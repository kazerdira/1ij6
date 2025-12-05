#!/usr/bin/env python3
"""
Production-Ready REST API v2
Incorporates ALL improvements: auth, rate limiting, validation, retries, caching, async

Usage:
    1. Install dependencies: pip install -r requirements.txt
    2. Start Redis: docker run -d -p 6379:6379 redis:alpine
    3. Run API: python api.py
    4. Open docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os
import logging
from datetime import datetime
import sys
import uuid
from contextvars import ContextVar

# Request ID context variable for tracing
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Add production folder to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security.auth import AuthManager, APIKeyManager, get_rate_limit
from security.rate_limiter import RateLimiter
from security.input_validator import (
    InputValidator,
    TranslationRequest,
    TranscriptionConfig,
    SecurityHeadersMiddleware
)
from reliability.circuit_breaker import circuit_breaker, async_circuit_breaker, registry as breaker_registry, CircuitBreakerError
from reliability.retry_handler import retry, RetryExhausted, AsyncRetryHandler
from reliability.health_checks import (
    health_monitor,
    initialize_health_checks,
    SystemResourceCheck,
    GPUHealthCheck
)
from scalability.async_translator import AsyncRealtimeTranslator
from scalability.cache_manager import (
    cache_manager,
    translation_cache,
    transcription_cache,
    hash_audio
)

# Configure logging with rotation
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
LOG_LEVEL = logging.WARNING if IS_PRODUCTION else logging.INFO

# Rotating file handler (10MB max, keep 5 backups)
file_handler = RotatingFileHandler(
    'logs/api.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI with API versioning
API_VERSION = "1.0.0"

app = FastAPI(
    title="Real-time Speech Translator API",
    description="Production-grade API with auth, rate limiting, caching, and monitoring",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/v1/openapi.json"
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS (configure appropriately for production)
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _allowed_origins == "*":
    cors_origins = ["*"]
    if IS_PRODUCTION:
        logger.warning("⚠️  CORS allows all origins! Set ALLOWED_ORIGINS for production.")
else:
    cors_origins = [origin.strip() for origin in _allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Global instances
translator: Optional[AsyncRealtimeTranslator] = None
rate_limiter = RateLimiter()
auth_manager = AuthManager()


# =============================================================================
# GLOBAL EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerError):
    """Handle circuit breaker errors - service unavailable"""
    request_id = request_id_var.get()
    logger.error(f"Circuit breaker open: {exc}", extra={"request_id": request_id})
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service Temporarily Unavailable",
            "message": "The service is experiencing high error rates. Please try again later.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "retry_after": 60
        },
        headers={"Retry-After": "60"}
    )


@app.exception_handler(RetryExhausted)
async def retry_exhausted_handler(request: Request, exc: RetryExhausted):
    """Handle retry exhaustion"""
    request_id = request_id_var.get()
    logger.error(f"Retry exhausted: {exc}", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Operation Failed",
            "message": "The operation failed after multiple attempts. Please try again later.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    request_id = request_id_var.get()
    logger.error(f"Unhandled exception: {exc}", extra={"request_id": request_id}, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
    )


# =============================================================================
# STARTUP / SHUTDOWN
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup WITH VALIDATION"""
    global translator
    
    logger.info("🚀 Starting API...")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    # Validate environment in production
    if IS_PRODUCTION:
        if not os.getenv("JWT_SECRET_KEY"):
            logger.critical("⚠️  SECURITY WARNING: JWT_SECRET_KEY not set in production!")
    
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Initialize translator
    translator = AsyncRealtimeTranslator(
        source_language=os.getenv("SOURCE_LANGUAGE", "ko"),
        target_language=os.getenv("TARGET_LANGUAGE", "eng_Latn"),
        whisper_model=os.getenv("WHISPER_MODEL", "base"),
        max_workers=int(os.getenv("MAX_WORKERS", "4"))
    )
    
    # Load models
    await translator.load_models()
    
    # Initialize health checks
    initialize_health_checks(translator=translator)
    
    logger.info("✅ API v2 started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global translator
    
    logger.info("🛑 Shutting down API...")
    
    if translator:
        await translator.cleanup()
    
    logger.info("✅ API shutdown complete")


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing"""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_var.set(request_id)
    
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        logger.error(f"Request {request_id} failed: {e}")
        raise


@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track active requests for rate limiting"""
    if cache_manager.enabled:
        try:
            cache_manager.redis_client.incr("active_requests")
        except:
            pass
    
    try:
        response = await call_next(request)
        return response
    finally:
        if cache_manager.enabled:
            try:
                cache_manager.redis_client.decr("active_requests")
            except:
                pass


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "name": "Real-time Speech Translator API",
        "version": API_VERSION,
        "status": "production",
        "environment": ENVIRONMENT,
        "features": [
            "Authentication (API keys + JWT)",
            "Rate limiting (tier-based)",
            "Input validation",
            "Circuit breakers",
            "Retry logic",
            "Caching",
            "Async processing",
            "Health monitoring",
            "Request tracing"
        ],
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Comprehensive health check
    
    Returns system health, model status, and resource usage
    """
    return await health_monitor.run_all_checks_async()


@app.get("/health/simple", tags=["Monitoring"])
async def simple_health_check():
    """Simple health check for load balancers"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Get system metrics
    """
    return {
        "translator": translator.get_stats() if translator else {},
        "cache": cache_manager.get_stats(),
        "circuit_breakers": breaker_registry.get_all_stats(),
        "rate_limiting": {
            "enabled": rate_limiter.enabled
        }
    }


@app.post("/auth/api-key", tags=["Authentication"])
async def create_api_key(
    user_id: str,
    tier: str = "free",
    admin_auth: dict = Depends(auth_manager.verify_admin)
):
    """
    Create new API key (admin only)
    
    Tiers:
    - free: 10 req/min, 1k/day
    - basic: 50 req/min, 10k/day
    - pro: 200 req/min, 100k/day
    - enterprise: 1000 req/min, 1M/day
    """
    try:
        api_key = APIKeyManager.generate_api_key(user_id, tier)
        limits = get_rate_limit(tier)
        
        return {
            "api_key": api_key,
            "user_id": user_id,
            "tier": tier,
            "rate_limits": limits,
            "created_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate/text", tags=["Translation"])
async def translate_text_endpoint(
    request: Request,
    translation_request: TranslationRequest,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    Translate text
    
    **Authentication required**
    
    Features:
    - Caching for repeated translations
    - Rate limiting based on user tier
    - Circuit breaker protection
    - Input validation
    """
    # Rate limiting
    tier = user.get("tier", "free")
    limits = get_rate_limit(tier)
    
    allowed, info = rate_limiter.check_rate_limit(
        request,
        user,
        max_requests=limits["requests_per_minute"],
        window_seconds=60
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": info["limit"],
                "remaining": info["remaining"],
                "reset": info["reset"]
            }
        )
    
    # Check cache
    cached = translation_cache.get_translation(
        text=translation_request.text,
        source_lang=translation_request.source_language,
        target_lang=translation_request.target_language
    )
    
    if cached:
        logger.info(f"Cache hit for translation: {translation_request.text[:50]}")
        return {
            "original": translation_request.text,
            "translated": cached,
            "source_language": translation_request.source_language,
            "target_language": translation_request.target_language,
            "cached": True,
            "timestamp": datetime.now().isoformat()
        }
    
    # Translate
    try:
        translated = await translator.translate_text(translation_request.text)
        
        # Cache result
        translation_cache.set_translation(
            text=translation_request.text,
            source_lang=translation_request.source_language,
            target_lang=translation_request.target_language,
            translation=translated,
            ttl=86400  # 24 hours
        )
        
        return {
            "original": translation_request.text,
            "translated": translated,
            "source_language": translation_request.source_language,
            "target_language": translation_request.target_language,
            "cached": False,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/audio", tags=["Transcription"])
async def transcribe_audio_endpoint(
    request: Request,
    file: UploadFile = File(...),
    source_language: str = "ko",
    target_language: str = "eng_Latn",
    translate: bool = True,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    Transcribe and translate audio file
    
    **Authentication required**
    
    Features:
    - Validates file format and size
    - Caches results by audio hash
    - Rate limiting
    - Circuit breaker protection
    """
    # Rate limiting
    tier = user.get("tier", "free")
    limits = get_rate_limit(tier)
    
    allowed, info = rate_limiter.check_rate_limit(
        request,
        user,
        max_requests=limits["requests_per_minute"],
        window_seconds=60
    )
    
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Validate input
    InputValidator.validate_language_code(source_language, "source_language")
    InputValidator.validate_language_code(target_language, "target_language")
    
    # Validate and read file
    audio_bytes = await InputValidator.validate_audio_file(file)
    
    # Check cache
    audio_hash_str = hash_audio(audio_bytes)
    cached_transcription = transcription_cache.get_transcription(
        audio_hash=audio_hash_str,
        language=source_language
    )
    
    if cached_transcription and translate:
        cached_translation = translation_cache.get_translation(
            text=cached_transcription,
            source_lang=source_language,
            target_lang=target_language
        )
        
        if cached_translation:
            logger.info(f"Full cache hit for audio transcription")
            return {
                "original": cached_transcription,
                "translated": cached_translation,
                "cached": True,
                "timestamp": datetime.now().isoformat()
            }
    
    # Process audio
    try:
        import soundfile as sf
        import numpy as np
        from io import BytesIO
        
        # Load audio
        audio_data, sample_rate = sf.read(BytesIO(audio_bytes))
        
        # Convert to mono
        if len(audio_data.shape) > 1:
            audio_data = audio_data[:, 0]
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            from scipy import signal
            num_samples = int(len(audio_data) * 16000 / sample_rate)
            audio_data = signal.resample(audio_data, num_samples)
        
        # Process
        original, translated = await translator.process_audio(audio_data)
        
        if not original:
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        # Cache results
        transcription_cache.set_transcription(
            audio_hash=audio_hash_str,
            language=source_language,
            transcription=original
        )
        
        if translate and translated:
            translation_cache.set_translation(
                text=original,
                source_lang=source_language,
                target_lang=target_language,
                translation=translated
            )
        
        return {
            "original": original,
            "translated": translated if translate else original,
            "source_language": source_language,
            "target_language": target_language if translate else source_language,
            "cached": False,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/cache/clear", tags=["Administration"])
async def clear_cache(
    pattern: Optional[str] = None,
    admin_auth: dict = Depends(auth_manager.verify_admin)
):
    """
    Clear cache (admin only)
    
    - pattern: Optional Redis pattern (e.g., "translation:*")
    - No pattern: Clear entire cache
    """
    try:
        if pattern:
            cache_manager.clear_pattern(pattern)
            return {"message": f"Cleared keys matching: {pattern}"}
        else:
            cache_manager.clear_all()
            return {"message": "Cache cleared completely"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/circuit-breaker/reset", tags=["Administration"])
async def reset_circuit_breakers(
    name: Optional[str] = None,
    admin_auth: dict = Depends(auth_manager.verify_admin)
):
    """
    Reset circuit breakers (admin only)
    
    - name: Optional breaker name to reset
    - No name: Reset all breakers
    """
    try:
        if name:
            breaker = breaker_registry.get(name)
            if breaker:
                breaker.reset()
                return {"message": f"Reset circuit breaker: {name}"}
            else:
                raise HTTPException(status_code=404, detail=f"Circuit breaker not found: {name}")
        else:
            breaker_registry.reset_all()
            return {"message": "All circuit breakers reset"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/languages", tags=["Configuration"])
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "whisper_languages": [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr",
            "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi"
        ],
        "nllb_languages": [
            "eng_Latn", "fra_Latn", "spa_Latn", "deu_Latn", "ita_Latn",
            "por_Latn", "rus_Cyrl", "jpn_Jpan", "kor_Hang", "zho_Hans",
            "ara_Arab", "hin_Deva"
        ]
    }


# =============================================================================
# DEVELOPMENT ENDPOINTS
# =============================================================================

@app.post("/dev/create-api-key", tags=["Development"])
async def create_dev_api_key(tier: str = "pro"):
    """
    Create API key for development/testing ONLY
    
    ⚠️ This endpoint is DISABLED in production!
    """
    if ENVIRONMENT not in ["development", "testing"]:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in development/testing mode"
        )
    
    try:
        # Generate key
        user_id = f"dev_user_{uuid.uuid4().hex[:8]}"
        test_key = APIKeyManager.generate_api_key(user_id, tier)
        limits = get_rate_limit(tier)
        
        return {
            "api_key": test_key,
            "user_id": user_id,
            "tier": tier,
            "rate_limits": limits,
            "warning": "⚠️ This is a DEVELOPMENT key. Do not use in production!",
            "usage": f'curl -H "X-API-Key: {test_key}" http://localhost:8000/translate/text',
            "created_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error creating dev API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Ensure Redis is running for caching and rate limiting
    # docker run -d -p 6379:6379 redis:alpine
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True
    )

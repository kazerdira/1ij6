🔧 Critical Fixes - Copy-Paste Ready Code
Fix #1: Apply Circuit Breakers to Critical Operations
File: production/scalability/async_translator.py
Replace the entire file with this version:
python#!/usr/bin/env python3
"""
Async Real-time Translator
Non-blocking async implementation for handling concurrent requests
WITH CIRCUIT BREAKERS AND RETRY LOGIC
"""

import asyncio
import numpy as np
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Handle imports gracefully
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Import circuit breaker and retry
from reliability.circuit_breaker import async_circuit_breaker, CircuitBreakerError
from reliability.retry_handler import async_retry, RetryExhausted


class AsyncRealtimeTranslator:
    """
    Async translator that can handle multiple requests concurrently
    Uses thread pool for CPU-bound operations (model inference)
    WITH CIRCUIT BREAKERS AND RETRY LOGIC
    """
    
    def __init__(
        self,
        source_language: str = "ko",
        target_language: str = "eng_Latn",
        whisper_model: str = "base",
        max_workers: int = 4
    ):
        """
        Initialize async translator
        
        Args:
            source_language: Source language code
            target_language: Target language code  
            whisper_model: Whisper model size
            max_workers: Max concurrent workers for model inference
        """
        self.source_language = source_language
        self.target_language = target_language
        self.whisper_model_name = whisper_model
        
        # Thread pool for CPU-bound model operations
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Models (loaded lazily)
        self.whisper_model = None
        self.translator_model = None
        self.translator_tokenizer = None
        
        # Device
        if TORCH_AVAILABLE:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = "cpu"
        
        # Lock for model operations
        self.model_lock = asyncio.Lock()
        
        # Statistics
        self.total_requests = 0
        self.active_requests = 0
        self.max_concurrent_requests = 0
        self.failed_requests = 0
        
        logger.info(f"AsyncRealtimeTranslator initialized on {self.device}")
    
    @async_retry(max_attempts=3, base_delay=2.0, exceptions=(OSError, RuntimeError, ConnectionError))
    async def load_models(self):
        """
        Load models asynchronously WITH RETRY LOGIC
        """
        if self.whisper_model is not None and self.translator_model is not None:
            return  # Already loaded
        
        if not WHISPER_AVAILABLE or not TRANSFORMERS_AVAILABLE:
            raise ImportError("whisper and transformers are required. Install with: pip install openai-whisper transformers")
        
        async with self.model_lock:
            # Double-check after acquiring lock
            if self.whisper_model is not None and self.translator_model is not None:
                return
            
            logger.info("Loading models with retry protection...")
            
            # Load in thread pool (blocking operations)
            loop = asyncio.get_event_loop()
            
            try:
                # Load Whisper
                logger.info(f"Loading Whisper model: {self.whisper_model_name}")
                self.whisper_model = await loop.run_in_executor(
                    self.executor,
                    whisper.load_model,
                    self.whisper_model_name
                )
                logger.info("Whisper model loaded successfully")
                
                # Load translator
                model_name = "facebook/nllb-200-distilled-600M"
                
                logger.info(f"Loading NLLB tokenizer: {model_name}")
                self.translator_tokenizer = await loop.run_in_executor(
                    self.executor,
                    AutoTokenizer.from_pretrained,
                    model_name
                )
                logger.info("NLLB tokenizer loaded successfully")
                
                logger.info(f"Loading NLLB model: {model_name}")
                self.translator_model = await loop.run_in_executor(
                    self.executor,
                    AutoModelForSeq2SeqLM.from_pretrained,
                    model_name
                )
                logger.info("NLLB model loaded successfully")
                
                # Move to GPU if available
                if self.device == "cuda" and TORCH_AVAILABLE:
                    logger.info("Moving translator model to GPU...")
                    self.translator_model = self.translator_model.to(self.device)
                    logger.info("Model moved to GPU")
                
                logger.info("All models loaded successfully")
            
            except Exception as e:
                logger.error(f"Error loading models: {e}")
                # Clear partially loaded models
                self.whisper_model = None
                self.translator_model = None
                self.translator_tokenizer = None
                raise
    
    @async_circuit_breaker(
        failure_threshold=5,
        recovery_timeout=60,
        name="whisper_transcribe"
    )
    async def transcribe_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio asynchronously WITH CIRCUIT BREAKER
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            Transcribed text
        """
        # Ensure models are loaded
        await self.load_models()
        
        # Normalize audio
        audio_float = audio_data.astype(np.float32)
        if audio_float.max() > 1.0 or audio_float.min() < -1.0:
            max_val = np.abs(audio_float).max()
            if max_val > 0:
                audio_float = audio_float / max_val
        
        # Run transcription in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        
        def _transcribe():
            try:
                result = self.whisper_model.transcribe(
                    audio_float,
                    language=self.source_language,
                    task="transcribe",
                    fp16=False
                )
                return result["text"].strip()
            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")
                raise
        
        transcribed_text = await loop.run_in_executor(
            self.executor,
            _transcribe
        )
        
        return transcribed_text
    
    @async_circuit_breaker(
        failure_threshold=5,
        recovery_timeout=60,
        name="nllb_translate"
    )
    async def translate_text(self, text: str) -> str:
        """
        Translate text asynchronously WITH CIRCUIT BREAKER
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        # Ensure models are loaded
        await self.load_models()
        
        if not text:
            return ""
        
        # Run translation in thread pool
        loop = asyncio.get_event_loop()
        
        def _translate():
            try:
                # Tokenize
                inputs = self.translator_tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                )
                
                # Move to GPU if available
                if self.device == "cuda" and TORCH_AVAILABLE:
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Get target language token ID
                target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(
                    self.target_language
                )
                
                # Generate translation
                with torch.no_grad():
                    translated_tokens = self.translator_model.generate(
                        **inputs,
                        forced_bos_token_id=target_lang_id,
                        max_length=512,
                        num_beams=5,
                        early_stopping=True
                    )
                
                # Decode
                translated_text = self.translator_tokenizer.batch_decode(
                    translated_tokens,
                    skip_special_tokens=True
                )[0]
                
                return translated_text
            
            except Exception as e:
                logger.error(f"Translation error: {e}")
                raise
        
        translated_text = await loop.run_in_executor(
            self.executor,
            _translate
        )
        
        return translated_text
    
    async def process_audio(self, audio_data: np.ndarray) -> Tuple[str, str]:
        """
        Process audio: transcribe and translate
        WITH ERROR HANDLING FOR CIRCUIT BREAKERS
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            (original_text, translated_text)
        """
        # Track concurrent requests
        self.active_requests += 1
        self.total_requests += 1
        self.max_concurrent_requests = max(
            self.max_concurrent_requests,
            self.active_requests
        )
        
        try:
            # Transcribe
            try:
                original = await self.transcribe_audio(audio_data)
            except CircuitBreakerError:
                logger.error("Transcription circuit breaker open - service unavailable")
                self.failed_requests += 1
                raise
            except RetryExhausted:
                logger.error("Transcription retry exhausted")
                self.failed_requests += 1
                raise
            
            if not original:
                return "", ""
            
            # Translate
            try:
                translated = await self.translate_text(original)
            except CircuitBreakerError:
                logger.error("Translation circuit breaker open - service unavailable")
                self.failed_requests += 1
                # Return transcription only if translation fails
                return original, ""
            except RetryExhausted:
                logger.error("Translation retry exhausted")
                self.failed_requests += 1
                return original, ""
            
            return original, translated
        
        except CircuitBreakerError:
            # Re-raise for API to handle
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing audio: {e}")
            self.failed_requests += 1
            raise
        finally:
            self.active_requests -= 1
    
    async def process_audio_batch(self, audio_list: list) -> list:
        """
        Process multiple audio samples concurrently
        
        Args:
            audio_list: List of audio numpy arrays
        
        Returns:
            List of (original, translated) tuples
        """
        tasks = [self.process_audio(audio) for audio in audio_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing audio {i}: {result}")
                processed_results.append(("", ""))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> dict:
        """Get translator statistics"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.failed_requests) / self.total_requests) * 100
        
        return {
            'total_requests': self.total_requests,
            'active_requests': self.active_requests,
            'max_concurrent_requests': self.max_concurrent_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(success_rate, 2),
            'device': self.device,
            'models_loaded': self.whisper_model is not None
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down translator...")
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clear GPU memory
        if self.device == "cuda" and TORCH_AVAILABLE:
            try:
                torch.cuda.empty_cache()
                logger.info("GPU memory cleared")
            except Exception as e:
                logger.error(f"Error clearing GPU memory: {e}")
        
        logger.info("AsyncRealtimeTranslator cleaned up")

Fix #2: Add Circuit Breaker to Cache Manager
File: production/scalability/cache_manager.py
Find the CacheManager.__init__ method (around line 50) and replace it with:
python    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600  # 1 hour
    ):
        """
        Initialize cache manager WITH CIRCUIT BREAKER
        
        Args:
            host: Redis host (uses REDIS_HOST env var if not provided)
            port: Redis port (uses REDIS_PORT env var if not provided)
            db: Redis database number
            password: Redis password (if required)
            default_ttl: Default time-to-live in seconds
        """
        self.redis_client = None
        self.enabled = False
        
        if not REDIS_AVAILABLE:
            logger.warning("Redis module not available. Caching disabled.")
            self.default_ttl = default_ttl
            self.hits = 0
            self.misses = 0
            self.sets = 0
            return
        
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", 6379))
        
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False,  # Handle binary data
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"Cache manager connected to Redis at {host}:{port}")
        
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None
            self.enabled = False
        
        self.default_ttl = default_ttl
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.sets = 0
        
        # Circuit breaker for Redis operations
        from reliability.circuit_breaker import CircuitBreaker
        self.redis_breaker = CircuitBreaker(
            name="redis_cache",
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception
        )
Then find the get method (around line 100) and replace with:
python    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache WITH CIRCUIT BREAKER
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        if not self.enabled:
            self.misses += 1
            return None
        
        try:
            with self.redis_breaker:
                value = self.redis_client.get(key)
                
                if value is None:
                    self.misses += 1
                    return None
                
                # Deserialize
                deserialized = pickle.loads(value)
                self.hits += 1
                
                logger.debug(f"Cache HIT: {key}")
                return deserialized
        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.misses += 1
            return None
And the set method (around line 130):
python    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache WITH CIRCUIT BREAKER
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = default)
        """
        if not self.enabled:
            return
        
        try:
            with self.redis_breaker:
                # Serialize
                serialized = pickle.dumps(value)
                
                # Set with TTL
                ttl = ttl or self.default_ttl
                self.redis_client.setex(key, ttl, serialized)
                
                self.sets += 1
                logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")

Fix #3: Fix Docker Health Check
File: production/Dockerfile
Replace lines 32-36 with:
dockerfile# Expose port for REST API
EXPOSE 8000

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Health check - give 2 minutes for model loading
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health/simple || exit 1

# Default command (can be overridden)
CMD ["python", "api.py"]

Fix #4: Add Better Error Handling to API
File: production/api.py
Add these imports at the top (after existing imports):
pythonfrom reliability.circuit_breaker import CircuitBreakerError
from reliability.retry_handler import RetryExhausted
from contextvars import ContextVar
import uuid
Add request ID tracking (after the CORS middleware section, around line 85):
python# Request ID context variable for tracing
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Middleware to add request IDs
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
Add global exception handlers (after app initialization, around line 90):
python# Global exception handlers
@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerError):
    """Handle circuit breaker errors"""
    logger.error(f"Circuit breaker open: {exc}", extra={"request_id": request_id_var.get()})
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service Temporarily Unavailable",
            "message": "The service is experiencing high error rates. Please try again later.",
            "request_id": request_id_var.get(),
            "timestamp": datetime.now().isoformat(),
            "retry_after": 60
        },
        headers={"Retry-After": "60"}
    )


@app.exception_handler(RetryExhausted)
async def retry_exhausted_handler(request: Request, exc: RetryExhausted):
    """Handle retry exhaustion"""
    logger.error(f"Retry exhausted: {exc}", extra={"request_id": request_id_var.get()})
    return JSONResponse(
        status_code=500,
        content={
            "error": "Operation Failed",
            "message": "The operation failed after multiple attempts. Please try again later.",
            "request_id": request_id_var.get(),
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with request ID"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": request_id_var.get(),
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"request_id": request_id_var.get()},
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id_var.get(),
            "timestamp": datetime.now().isoformat()
        }
    )

Fix #5: Update API Endpoints to Handle Circuit Breaker Errors
File: production/api.py
Update the translate_text_endpoint function (around line 157):
python@app.post("/translate/text", tags=["Translation"])
async def translate_text_endpoint(
    request: Request,
    translation_request: TranslationRequest,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    Translate text WITH CIRCUIT BREAKER PROTECTION
    
    **Authentication required**
    
    Features:
    - Caching for repeated translations
    - Rate limiting based on user tier
    - Circuit breaker protection
    - Input validation
    """
    request_id = request_id_var.get()
    logger.info(
        f"Translation request received",
        extra={
            "request_id": request_id,
            "user_id": user.get("user_id"),
            "text_length": len(translation_request.text)
        }
    )
    
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
        logger.info(f"Cache hit for translation", extra={"request_id": request_id})
        return {
            "original": translation_request.text,
            "translated": cached,
            "source_language": translation_request.source_language,
            "target_language": translation_request.target_language,
            "cached": True,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
    
    # Translate with circuit breaker protection
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
        
        logger.info(f"Translation successful", extra={"request_id": request_id})
        
        return {
            "original": translation_request.text,
            "translated": translated,
            "source_language": translation_request.source_language,
            "target_language": translation_request.target_language,
            "cached": False,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except CircuitBreakerError as e:
        # Will be handled by global exception handler
        raise
    
    except Exception as e:
        logger.error(
            f"Translation error: {e}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )
Update the transcribe_audio_endpoint function (around line 220):
python@app.post("/transcribe/audio", tags=["Transcription"])
async def transcribe_audio_endpoint(
    request: Request,
    file: UploadFile = File(...),
    source_language: str = "ko",
    target_language: str = "eng_Latn",
    translate: bool = True,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    Transcribe and translate audio file WITH CIRCUIT BREAKER PROTECTION
    
    **Authentication required**
    
    Features:
    - Validates file format and size
    - Caches results by audio hash
    - Rate limiting
    - Circuit breaker protection
    """
    request_id = request_id_var.get()
    logger.info(
        f"Transcription request received",
        extra={
            "request_id": request_id,
            "user_id": user.get("user_id"),
            "filename": file.filename
        }
    )
    
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
            logger.info(f"Full cache hit for audio transcription", extra={"request_id": request_id})
            return {
                "original": cached_transcription,
                "translated": cached_translation,
                "cached": True,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat()
            }
    
    # Process audio with circuit breaker protection
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
        
        # Process with circuit breaker protection
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
        
        logger.info(f"Transcription successful", extra={"request_id": request_id})
        
        return {
            "original": original,
            "translated": translated if translate else original,
            "source_language": source_language,
            "target_language": target_language if translate else source_language,
            "cached": False,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except CircuitBreakerError as e:
        # Will be handled by global exception handler
        raise
    except Exception as e:
        logger.error(
            f"Transcription error: {e}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))

Fix #6: Add Development API Key Generator
File: production/api.py
Add this endpoint before the if __name__ == "__main__" block:
python@app.post("/dev/create-api-key", tags=["Development"])
async def create_dev_api_key(tier: str = "pro"):
    """
    Create API key for development ONLY
    
    **WARNING: This endpoint should be DISABLED in production!**
    """
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in development mode"
        )
    
    try:
        from security.auth import APIKeyManager
        
        # Generate key
        test_key = APIKeyManager.generate_api_key(f"dev_user_{uuid.uuid4().hex[:8]}", tier)
        limits = get_rate_limit(tier)
        
        return {
            "api_key": test_key,
            "tier": tier,
            "rate_limits": limits,
            "warning": "⚠️  This is a DEVELOPMENT key. Do not use in production!",
            "usage": f'Use this key in request headers: -H "X-API-Key: {test_key}"',
            "created_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error creating dev API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

Fix #7: Update Health Check to Include Circuit Breaker Status
File: production/api.py
Replace the /metrics endpoint (around line 135) with:
python@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Get comprehensive system metrics including circuit breaker status
    """
    translator_stats = translator.get_stats() if translator else {}
    cache_stats = cache_manager.get_stats()
    
    # Get circuit breaker stats
    from reliability.circuit_breaker import registry as breaker_registry
    circuit_breaker_stats = breaker_registry.get_all_stats()
    
    return {
        "translator": translator_stats,
        "cache": cache_stats,
        "circuit_breakers": circuit_breaker_stats,
        "rate_limiting": {
            "enabled": rate_limiter.enabled
        },
        "timestamp": datetime.now().isoformat()
    }

Fix #8: Add Startup Validation
File: production/api.py
Update the startup_event function (around line 100) to:
python@app.on_event("startup")
async def startup_event():
    """Initialize on startup WITH VALIDATION"""
    global translator
    
    logger.info("🚀 Starting API v2...")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Log level: {LOG_LEVEL}")
    
    # Validate environment
    if IS_PRODUCTION:
        # Check critical environment variables
        if os.getenv("JWT_SECRET_KEY") == "change-me-in-production":
            logger.critical("⚠️  SECURITY WARNING: JWT_SECRET_KEY not set properly in production!")
        
        if os.getenv("ALLOWED_ORIGINS") == "*":
            logger.warning("⚠️  CORS allows all origins in production!")
    
    # Create required directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Initialize translator with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing translator (attempt {attempt + 1}/{max_retries})...")
            
            translator = AsyncRealtimeTranslator(
                source_language=os.getenv("SOURCE_LANGUAGE", "ko"),
                target_language=os.getenv("TARGET_LANGUAGE", "eng_Latn"),
                whisper_model=os.getenv("WHISPER_MODEL", "base"),
                max_workers=int(os.getenv("MAX_WORKERS", "4"))
            )
            
            # Load models
            logger.info("Loading models...")
            await translator.load_models()
            logger.info("✅ Models loaded successfully")
            
            break  # Success
        
        except Exception as e:
            logger.error(f"Failed to initialize translator: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                logger.critical("❌ Failed to initialize translator after all retries")
                raise
    
    # Initialize health checks
    initialize_health_checks(translator=translator, redis_client=cache_manager.redis_client)
    
    # Check Redis
    if cache_manager.enabled:
        logger.info("✅ Redis connected - caching enabled")
    else:
        logger.warning("⚠️  Redis not available - caching disabled")
    
    if rate_limiter.enabled:
        logger.info("✅ Redis connected - rate limiting enabled")
    else:
        logger.warning("⚠️  Redis not available - rate limiting disabled")
    
    logger.info("✅ API v2 started successfully")
    logger.info(f"📖 API documentation available at: http://localhost:8000/docs")

Fix #9: Add Better Logging Configuration
File: production/api.py
Replace the logging configuration section (around line 30) with:
python# Configure logging with rotation and better formatting
from logging.handlers import RotatingFileHandler
import sys

os.makedirs("logs", exist_ok=True)

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
LOG_LEVEL = logging.WARNING if IS_PRODUCTION else logging.INFO

# Custom formatter with request ID
class RequestIdFormatter(logging.Formatter):
    """Add request ID to log records"""
    def format(self, record):
        # Get request ID from context
        request_id = request_id_var.get() if 'request_id_var' in globals() else "no-request-id"
        record.request_id = request_id
        return super().format(record)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(RequestIdFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
))

# File handler with rotation (10MB max, keep 5 backups)
file_handler = RotatingFileHandler(
    'logs/api.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(RequestIdFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
))

# Configure root logger
logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("whisper").setLevel(logging.WARNING)

Summary of Changes
Files Modified:

✅ production/scalability/async_translator.py - Added circuit breakers and retry logic
✅ production/scalability/cache_manager.py - Added circuit breaker for Redis
✅ production/Dockerfile - Fixed health check
✅ production/api.py - Added error handlers, request IDs, better logging, validation

What These Fixes Do:

Circuit Breakers: Prevent cascading failures when models fail
Retry Logic: Automatically retry failed operations with exponential backoff
Request Tracing: Track requests with unique IDs
Error Handling: Graceful degradation with clear error messages
Health Checks: Reliable Docker health checks
Redis Resilience: Continue working if Redis goes down
Development Tools: Easy API key generation for testing
Better Logging: Includes request IDs and proper rotation

Testing Your Fixes:
bash# 1. Start the services
cd production
docker-compose up --build

# 2. Wait for models to load (check logs)
docker-compose logs -f api

# 3. Create a test API key (in another terminal)
curl -X POST http://localhost:8000/dev/create-api-key?tier=pro

# 4. Test translation
curl -X POST http://localhost:8000/translate/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY_HERE" \
  -d '{
    "text": "안녕하세요",
    "source_language": "ko",
    "target_language": "eng_Latn"
  }'

# 5. Check circuit breaker status
curl http://localhost:8000/metrics

# 6. Test health check
curl http://localhost:8000/health
What to Look For:
✅ Models load successfully
✅ Circuit breakers start in "closed" state
✅ Request IDs appear in logs
✅ Errors are handled gracefully
✅ Redis failures don't crash the API
✅ Health check returns 200 OK
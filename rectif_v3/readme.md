🔴 PRIORITY 0: CRITICAL SECURITY FIXES (Deploy Immediately)
Fix #1: Replace Pickle with JSON in Cache (CRITICAL - RCE Risk)
File: production/scalability/cache_manager.py
Replace the entire serialization section:
python#!/usr/bin/env python3
"""
Cache Manager with Redis
SECURE VERSION - Uses JSON instead of pickle
"""

import hashlib
import json
from typing import Optional, Any
import logging
import os

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from reliability.circuit_breaker import CircuitBreaker


class SecureJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for complex types"""
    def default(self, obj):
        if isinstance(obj, bytes):
            return {"__type__": "bytes", "data": obj.hex()}
        if hasattr(obj, 'tolist'):  # numpy arrays
            return {"__type__": "numpy", "data": obj.tolist()}
        return super().default(obj)


def secure_json_decoder(dct):
    """Custom JSON decoder"""
    if "__type__" in dct:
        if dct["__type__"] == "bytes":
            return bytes.fromhex(dct["data"])
        if dct["__type__"] == "numpy":
            import numpy as np
            return np.array(dct["data"])
    return dct


class CacheManager:
    """Redis-based cache manager - SECURE VERSION with JSON"""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600
    ):
        self.redis_client = None
        self.enabled = False
        self.default_ttl = default_ttl
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.sets = 0
        
        # Circuit breaker
        self.redis_breaker = CircuitBreaker(
            name="redis_cache",
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception
        )
        
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available. Caching disabled.")
            return
        
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", 6379))
        
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,  # IMPORTANT: Decode to strings for JSON
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"✅ Secure cache manager connected to Redis at {host}:{port}")
        
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None
            self.enabled = False
    
    def _generate_key(self, prefix: str, data: Any) -> str:
        """Generate cache key"""
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, sort_keys=True, cls=SecureJSONEncoder)
        
        hash_hex = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_hex}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache - SECURE with JSON"""
        if not self.enabled:
            self.misses += 1
            return None
        
        try:
            with self.redis_breaker:
                value = self.redis_client.get(key)
                
                if value is None:
                    self.misses += 1
                    return None
                
                # Deserialize from JSON (SECURE)
                try:
                    deserialized = json.loads(value, object_hook=secure_json_decoder)
                    self.hits += 1
                    logger.debug(f"Cache HIT: {key}")
                    return deserialized
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize cache value: {e}")
                    self.misses += 1
                    return None
        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache - SECURE with JSON"""
        if not self.enabled:
            return
        
        try:
            with self.redis_breaker:
                # Serialize to JSON (SECURE)
                try:
                    serialized = json.dumps(value, cls=SecureJSONEncoder)
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to serialize value for caching: {e}")
                    return
                
                ttl = ttl or self.default_ttl
                self.redis_client.setex(key, ttl, serialized)
                
                self.sets += 1
                logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        if not self.enabled:
            return
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    def clear_pattern(self, pattern: str):
        """Clear keys matching pattern"""
        if not self.enabled:
            return
        
        try:
            keys = list(self.redis_client.scan_iter(pattern))  # Use scan_iter for large sets
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} keys matching: {pattern}")
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
    
    def clear_all(self):
        """Clear entire cache"""
        if not self.enabled:
            return
        
        try:
            self.redis_client.flushdb()
            logger.info("Cache cleared (flushdb)")
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'enabled': self.enabled,
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'hit_rate': round(hit_rate, 2),
            'serialization': 'JSON (secure)'  # Indicate secure serialization
        }
        
        if self.enabled:
            try:
                info = self.redis_client.info()
                stats['redis_memory_used_mb'] = round(
                    info.get('used_memory', 0) / (1024 * 1024), 2
                )
                stats['redis_connected_clients'] = info.get('connected_clients', 0)
            except Exception:
                pass
        
        return stats


# Rest of the file remains the same (TranslationCache, TranscriptionCache, hash_audio)
class TranslationCache:
    """Specialized cache for translations"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.prefix = "translation"
    
    def get_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        cache_data = {'text': text, 'source': source_lang, 'target': target_lang}
        key = self.cache._generate_key(self.prefix, cache_data)
        return self.cache.get(key)
    
    def set_translation(self, text: str, source_lang: str, target_lang: str, translation: str, ttl: int = 86400):
        cache_data = {'text': text, 'source': source_lang, 'target': target_lang}
        key = self.cache._generate_key(self.prefix, cache_data)
        self.cache.set(key, translation, ttl)


class TranscriptionCache:
    """Specialized cache for audio transcriptions"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.prefix = "transcription"
    
    def get_transcription(self, audio_hash: str, language: str) -> Optional[str]:
        cache_data = {'audio_hash': audio_hash, 'language': language}
        key = self.cache._generate_key(self.prefix, cache_data)
        return self.cache.get(key)
    
    def set_transcription(self, audio_hash: str, language: str, transcription: str, ttl: int = 86400):
        cache_data = {'audio_hash': audio_hash, 'language': language}
        key = self.cache._generate_key(self.prefix, cache_data)
        self.cache.set(key, transcription, ttl)


def hash_audio(audio_data: bytes) -> str:
    """Generate hash for audio data"""
    return hashlib.sha256(audio_data).hexdigest()


# Global cache instance
cache_manager = CacheManager()
translation_cache = TranslationCache(cache_manager)
transcription_cache = TranscriptionCache(cache_manager)

Fix #2: Hash API Keys (Security)
File: production/security/auth.py
Replace the API key storage section:
python#!/usr/bin/env python3
"""
Authentication System - SECURE VERSION with hashed API keys
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import jwt
from datetime import datetime, timedelta, timezone  # FIXED: Use timezone-aware datetime
import hashlib
import secrets
import redis
import os
import bcrypt  # ADD THIS: pip install bcrypt

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    print("⚠️  WARNING: JWT_SECRET_KEY not set! Using auto-generated key")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# Redis connection
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False
    print("⚠️  Redis not available")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def hash_api_key(api_key: str) -> str:
    """
    Hash API key using bcrypt (SECURE)
    
    Args:
        api_key: Plain API key
    
    Returns:
        Bcrypt hash
    """
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key_hash(api_key: str, hashed: str) -> bool:
    """
    Verify API key against hash
    
    Args:
        api_key: Plain API key
        hashed: Bcrypt hash
    
    Returns:
        True if match
    """
    try:
        return bcrypt.checkpw(api_key.encode(), hashed.encode())
    except Exception:
        return False


class APIKeyManager:
    """Manage API keys - SECURE VERSION with hashing"""
    
    @staticmethod
    def generate_api_key(user_id: str, tier: str = "free") -> str:
        """
        Generate a new API key
        
        Returns the PLAIN key (user sees this once)
        Stores HASHED version in Redis
        """
        if not REDIS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Redis not available")
        
        # Generate plain key
        plain_key = f"tr_{secrets.token_urlsafe(32)}"
        
        # Hash it
        hashed_key = hash_api_key(plain_key)
        
        # Create lookup index: hash of first 16 chars for fast lookup
        key_prefix = hashlib.sha256(plain_key[:16].encode()).hexdigest()[:16]
        
        # Store metadata with HASHED key
        key_data = {
            "user_id": user_id,
            "tier": tier,
            "hashed_key": hashed_key,
            "key_prefix": key_prefix,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requests_today": 0,
            "total_requests": 0,
            "last_rotated": datetime.now(timezone.utc).isoformat()
        }
        
        # Store by prefix for lookup
        redis_client.hset(f"api_key_meta:{key_prefix}", mapping=key_data)
        
        # Add to user's key list (store prefix only)
        redis_client.sadd(f"user_keys:{user_id}", key_prefix)
        
        # Return PLAIN key (user sees this once and must save it)
        return plain_key
    
    @staticmethod
    def validate_api_key(api_key: str) -> Optional[Dict]:
        """
        Validate API key - SECURE VERSION
        
        1. Extract prefix from plain key
        2. Look up metadata by prefix
        3. Verify against bcrypt hash
        """
        if not REDIS_AVAILABLE or not api_key or not api_key.startswith("tr_"):
            return None
        
        # Get key prefix for lookup
        key_prefix = hashlib.sha256(api_key[:16].encode()).hexdigest()[:16]
        
        # Get metadata
        key_data = redis_client.hgetall(f"api_key_meta:{key_prefix}")
        
        if not key_data:
            return None
        
        # Verify hash
        stored_hash = key_data.get("hashed_key")
        if not stored_hash or not verify_api_key_hash(api_key, stored_hash):
            return None
        
        # Increment usage
        redis_client.hincrby(f"api_key_meta:{key_prefix}", "requests_today", 1)
        redis_client.hincrby(f"api_key_meta:{key_prefix}", "total_requests", 1)
        redis_client.hset(f"api_key_meta:{key_prefix}", "last_used", datetime.now(timezone.utc).isoformat())
        
        return key_data
    
    @staticmethod
    def rotate_api_key(old_api_key: str) -> str:
        """
        Rotate API key (generate new, invalidate old)
        
        Returns new plain key
        """
        if not REDIS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Redis not available")
        
        # Validate old key
        old_key_data = APIKeyManager.validate_api_key(old_api_key)
        if not old_key_data:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        user_id = old_key_data.get("user_id")
        tier = old_key_data.get("tier")
        
        # Generate new key
        new_key = APIKeyManager.generate_api_key(user_id, tier)
        
        # Revoke old key
        old_prefix = hashlib.sha256(old_api_key[:16].encode()).hexdigest()[:16]
        redis_client.delete(f"api_key_meta:{old_prefix}")
        redis_client.srem(f"user_keys:{user_id}", old_prefix)
        
        return new_key
    
    @staticmethod
    def revoke_api_key(api_key: str) -> bool:
        """Revoke an API key"""
        if not REDIS_AVAILABLE:
            return False
        
        key_prefix = hashlib.sha256(api_key[:16].encode()).hexdigest()[:16]
        key_data = redis_client.hgetall(f"api_key_meta:{key_prefix}")
        
        if not key_data:
            return False
        
        user_id = key_data.get("user_id")
        
        redis_client.delete(f"api_key_meta:{key_prefix}")
        redis_client.srem(f"user_keys:{user_id}", key_prefix)
        
        return True
    
    @staticmethod
    def get_user_keys(user_id: str) -> list:
        """Get all key prefixes for a user (NOT full keys)"""
        if not REDIS_AVAILABLE:
            return []
        
        prefixes = list(redis_client.smembers(f"user_keys:{user_id}"))
        
        # Return metadata for each key
        keys_info = []
        for prefix in prefixes:
            key_data = redis_client.hgetall(f"api_key_meta:{prefix}")
            if key_data:
                keys_info.append({
                    "prefix": prefix,
                    "tier": key_data.get("tier"),
                    "created_at": key_data.get("created_at"),
                    "last_used": key_data.get("last_used", "never"),
                    "total_requests": key_data.get("total_requests", 0)
                })
        
        return keys_info


class JWTManager:
    """Manage JWT tokens - FIXED datetime"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta  # FIXED
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)  # FIXED
        
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None


class AuthManager:
    """Combined authentication manager"""
    
    @staticmethod
    async def verify_request(
        api_key: Optional[str] = Security(api_key_header),
        bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
    ) -> Dict:
        """Verify request authentication"""
        
        # Try API key
        if api_key:
            user_data = APIKeyManager.validate_api_key(api_key)
            if user_data:
                return user_data
        
        # Try JWT
        if bearer:
            payload = JWTManager.verify_token(bearer.credentials)
            if payload:
                return payload
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    @staticmethod
    async def verify_admin(
        api_key: Optional[str] = Security(api_key_header),
        bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
    ) -> Dict:
        """Verify admin authentication"""
        user_data = await AuthManager.verify_request(api_key, bearer)
        
        if user_data.get("role") != "admin" and user_data.get("tier") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        return user_data


# Rate limits
RATE_LIMITS = {
    "free": {"requests_per_minute": 10, "requests_per_day": 1000},
    "basic": {"requests_per_minute": 50, "requests_per_day": 10000},
    "pro": {"requests_per_minute": 200, "requests_per_day": 100000},
    "enterprise": {"requests_per_minute": 1000, "requests_per_day": 1000000},
    "admin": {"requests_per_minute": 10000, "requests_per_day": 10000000}
}


def get_rate_limit(tier: str) -> Dict:
    """Get rate limits for tier"""
    return RATE_LIMITS.get(tier, RATE_LIMITS["free"])

Fix #3: Hard-Fail on CORS Misconfiguration
File: production/api.py
Replace CORS configuration section (around line 85):
python# CORS Configuration - STRICT VALIDATION
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")

# CRITICAL: Hard fail in production if CORS is not configured properly
if IS_PRODUCTION and _allowed_origins == "*":
    logger.critical("❌ FATAL: CORS allows all origins (*) in PRODUCTION!")
    logger.critical("❌ Set ALLOWED_ORIGINS environment variable to specific domains")
    logger.critical("❌ Example: ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com")
    raise RuntimeError("CORS misconfiguration - cannot start in production with ALLOWED_ORIGINS=*")

if _allowed_origins == "*":
    cors_origins = ["*"]
    logger.warning("⚠️  CORS allows ALL origins - OK for development only")
else:
    cors_origins = [origin.strip() for origin in _allowed_origins.split(",")]
    logger.info(f"✅ CORS configured for: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

🟠 PRIORITY 1: OPERATIONAL IMPROVEMENTS
Fix #4: Prometheus Metrics Export
File: production/monitoring/prometheus_metrics.py (NEW FILE)
python#!/usr/bin/env python3
"""
Prometheus Metrics Exporter
Provides /metrics endpoint in Prometheus format
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, REGISTRY
from prometheus_client.exposition import make_asgi_app
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# METRICS DEFINITIONS
# =============================================================================

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Translation metrics
translations_total = Counter(
    'translations_total',
    'Total translations processed',
    ['source_lang', 'target_lang', 'cached']
)

translation_duration_seconds = Histogram(
    'translation_duration_seconds',
    'Translation processing time',
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Transcription metrics
transcriptions_total = Counter(
    'transcriptions_total',
    'Total transcriptions processed',
    ['language', 'cached']
)

transcription_duration_seconds = Histogram(
    'transcription_duration_seconds',
    'Transcription processing time',
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
)

# Cache metrics
cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # operation: get/set/delete, result: hit/miss/error
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['name']
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['name']
)

# Model metrics
model_loaded = Gauge(
    'model_loaded',
    'Model load status (1=loaded, 0=not loaded)',
    ['model_name']
)

model_inference_duration_seconds = Histogram(
    'model_inference_duration_seconds',
    'Model inference time',
    ['model_name'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

# System metrics
active_requests = Gauge(
    'active_requests',
    'Number of active requests'
)

# Rate limiting metrics
rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Total rate limit violations',
    ['tier']
)

# API key metrics
api_key_usage_total = Counter(
    'api_key_usage_total',
    'API key usage',
    ['user_id', 'tier']
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'endpoint']
)

# Application info
app_info = Info('app', 'Application information')
app_info.info({
    'version': '1.0.0',
    'environment': 'production'
})


# =============================================================================
# METRICS HELPER FUNCTIONS
# =============================================================================

class MetricsHelper:
    """Helper class for recording metrics"""
    
    @staticmethod
    def record_request(method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    @staticmethod
    def record_translation(source_lang: str, target_lang: str, cached: bool, duration: float):
        """Record translation metrics"""
        translations_total.labels(
            source_lang=source_lang,
            target_lang=target_lang,
            cached='true' if cached else 'false'
        ).inc()
        translation_duration_seconds.observe(duration)
    
    @staticmethod
    def record_transcription(language: str, cached: bool, duration: float):
        """Record transcription metrics"""
        transcriptions_total.labels(
            language=language,
            cached='true' if cached else 'false'
        ).inc()
        transcription_duration_seconds.observe(duration)
    
    @staticmethod
    def record_cache_operation(operation: str, result: str):
        """Record cache operation"""
        cache_operations_total.labels(operation=operation, result=result).inc()
    
    @staticmethod
    def update_circuit_breaker_state(name: str, state: str):
        """Update circuit breaker state"""
        state_map = {'closed': 0, 'open': 1, 'half_open': 2}
        circuit_breaker_state.labels(name=name).set(state_map.get(state, 0))
    
    @staticmethod
    def record_circuit_breaker_failure(name: str):
        """Record circuit breaker failure"""
        circuit_breaker_failures_total.labels(name=name).inc()
    
    @staticmethod
    def update_model_status(model_name: str, loaded: bool):
        """Update model load status"""
        model_loaded.labels(model_name=model_name).set(1 if loaded else 0)
    
    @staticmethod
    def record_model_inference(model_name: str, duration: float):
        """Record model inference time"""
        model_inference_duration_seconds.labels(model_name=model_name).observe(duration)
    
    @staticmethod
    def set_active_requests(count: int):
        """Set active requests gauge"""
        active_requests.set(count)
    
    @staticmethod
    def record_rate_limit_exceeded(tier: str):
        """Record rate limit violation"""
        rate_limit_exceeded_total.labels(tier=tier).inc()
    
    @staticmethod
    def record_api_key_usage(user_id: str, tier: str):
        """Record API key usage"""
        api_key_usage_total.labels(user_id=user_id, tier=tier).inc()
    
    @staticmethod
    def record_error(error_type: str, endpoint: str):
        """Record error"""
        errors_total.labels(error_type=error_type, endpoint=endpoint).inc()


# Create Prometheus ASGI app for /metrics endpoint
metrics_app = make_asgi_app()


# Export metrics helper
__all__ = ['MetricsHelper', 'metrics_app']
Update production/api.py to mount metrics endpoint:
python# Add at the top with other imports
from monitoring.prometheus_metrics import MetricsHelper, metrics_app
import time

# Mount Prometheus metrics endpoint
app.mount("/metrics", metrics_app)

# Add middleware to track requests
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics"""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        MetricsHelper.record_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration
        )
        
        return response
    
    except Exception as e:
        duration = time.time() - start_time
        MetricsHelper.record_request(
            method=request.method,
            endpoint=request.url.path,
            status=500,
            duration=duration
        )
        MetricsHelper.record_error(
            error_type=type(e).__name__,
            endpoint=request.url.path
        )
        raise
Add to requirements.txt:
txtprometheus-client==0.19.0

Fix #5: Add Graceful Degradation for Model Loading
File: production/api.py
Replace startup_event function:
python@app.on_event("startup")
async def startup_event():
    """Initialize on startup WITH GRACEFUL DEGRADATION"""
    global translator
    
    logger.info("🚀 Starting API...")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    # Validate production environment
    if IS_PRODUCTION:
        if not os.getenv("JWT_SECRET_KEY"):
            logger.critical("❌ FATAL: JWT_SECRET_KEY not set in production!")
            raise RuntimeError("JWT_SECRET_KEY required in production")
        
        if os.getenv("ALLOWED_ORIGINS") == "*":
            logger.critical("❌ FATAL: CORS allows all origins in production!")
            raise RuntimeError("CORS misconfiguration")
    
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Initialize translator WITH FALLBACK
    max_retries = 3
    model_load_success = False
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Loading models (attempt {attempt + 1}/{max_retries})...")
            
            translator = AsyncRealtimeTranslator(
                source_language=os.getenv("SOURCE_LANGUAGE", "ko"),
                target_language=os.getenv("TARGET_LANGUAGE", "eng_Latn"),
                whisper_model=os.getenv("WHISPER_MODEL", "base"),
                max_workers=int(os.getenv("MAX_WORKERS", "4"))
            )
            
            await translator.load_models()
            model_load_success = True
            logger.info("✅ Models loaded successfully")
            break
        
        except Exception as e:
            logger.error(f"Model loading failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
    
    # GRACEFUL DEGRADATION: Start API even if models fail
    if not model_load_success:
        logger.warning("⚠️  Models failed to load - API starting in DEGRADED MODE")
        logger.warning("⚠️  Translation endpoints will return 503 errors")
        translator = None  # Set to None to indicate degraded state
    
    # Initialize health checks
    initialize_health_checks(translator=translator, redis_client=cache_manager.redis_client)
    
    # Check dependencies
    if cache_manager.enabled:
        logger.info("✅ Redis connected - caching enabled")
    else:
        logger.warning("⚠️  Redis unavailable - caching disabled")
    
    if rate_limiter.enabled:
        logger.info("✅ Rate limiting enabled")
    else:
        logger.warning("⚠️  Rate limiting disabled")
    
    logger.info(f"✅ API started (models: {'loaded' if model_load_success else 'DEGRADED'})")
Add degraded mode check to translation endpoints:
python@app.post("/translate/text", tags=["Translation"])
async def translate_text_endpoint(
    request: Request,
    translation_request: TranslationRequest,
    user: dict = Depends(auth_manager.verify_request)
):
    """Translate text WITH DEGRADED MODE CHECK"""
    
    # Check if models are loaded
    if translator is None or not translator.whisper_model:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service Degraded",
                "message": "Translation models are not available. Please try again later.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    # ... rest of endpoint code

🟡 PRIORITY 2: BUSINESS LOGIC
Fix #6: Add API Key Rotation Endpoint
File: production/api.py
Add new endpoint:
python@app.post("/auth/rotate-api-key", tags=["Authentication"])
async def rotate_api_key_endpoint(
    request: Request,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    Rotate API key (generate new, invalidate old)
    
    **Authentication required (using old key)**
    
    Returns new API key - SAVE IT IMMEDIATELY!
    """
    # Get old API key from request
    old_key = request.headers.get("X-API-Key")
    
    if not old_key:
        raise HTTPException(
            status_code=400,
            detail="API key required in X-API-Key header"
        )
    
    try:
        # Rotate key
        new_key = APIKeyManager.rotate_api_key(old_key)
        
        return {
            "message": "API key rotated successfully",
            "new_api_key": new_key,
            "warning": "⚠️  Save this key immediately! Old key is now invalid.",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            "rotated_at": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Key rotation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/my-keys", tags=["Authentication"])
async def list_my_keys(
    request: Request,
    user: dict = Depends(auth_manager.verify_request)
):
    """
    List all API keys for current user
    
    Returns key metadata (not full keys)
    """
    user_id = user.get("user_id")
    
    try:
        keys = APIKeyManager.get_user_keys(user_id)
        
        return {
            "user_id": user_id,
            "total_keys": len(keys),
            "keys": keys,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to list keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

Fix #7: Add Usage Quotas Enforcement
File: production/security/usage_quotas.py (NEW FILE)
python#!/usr/bin/env python3
"""
Usage Quotas Enforcement
Hard limits on daily usage with billing integration hooks
"""

from typing import Dict, Tuple
import redis
import os
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Redis client
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False


# Daily quotas by tier
DAILY_QUOTAS = {
    "free": {
        "requests": 1000,
        "compute_seconds": 300,  # 5 minutes
        "audio_minutes": 10
    },
    "basic": {
        "requests": 10000,
        "compute_seconds": 3000,  # 50 minutes
        "audio_minutes": 100
    },
    "pro": {
        "requests": 100000,
        "compute_seconds": 30000,  # 500 minutes
        "audio_minutes": 1000
    },
    "enterprise": {
        "requests": 1000000,
        "compute_seconds": 300000,  # 5000 minutes
        "audio_minutes": 10000
    }
}


class UsageQuotaManager:
    """Enforce usage quotas with billing hooks"""
    
    @staticmethod
    def check_quota(user_id: str, tier: str, resource: str = "requests") -> Tuple[bool, Dict]:
        """
        Check if user has quota remaining
        
        Args:
            user_id: User ID
            tier: User tier
            resource: Resource type (requests/compute_seconds/audio_minutes)
        
        Returns:
            (allowed, info)
        """
        if not REDIS_AVAILABLE:
            return True, {"quota_check": "disabled"}
        
        quotas = DAILY_QUOTAS.get(tier, DAILY_QUOTAS["free"])
        max_quota = quotas.get(resource, 0)
        
        # Get usage key
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage_key = f"quota:{user_id}:{resource}:{today}"
        
        # Get current usage
        current_usage = int(redis_client.get(usage_key) or 0)
        
        # Check quota
        allowed = current_usage < max_quota
        remaining = max(0, max_quota - current_usage)
        
        info = {
            "resource": resource,
            "quota": max_quota,
            "used": current_usage,
            "remaining": remaining,
            "reset_at": (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)).isoformat()
        }
        
        return allowed, info
    
    @staticmethod
    def increment_usage(
        user_id: str,
        tier: str,
        resource: str = "requests",
        amount: int = 1
    ):
        """
        Increment usage counter
        
        Args:
            user_id: User ID
            tier: User tier
            resource: Resource type
            amount: Amount to increment
        """
        if not REDIS_AVAILABLE:
            return
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage_key = f"quota:{user_id}:{resource}:{today}"
        
        # Increment
        new_usage = redis_client.incrby(usage_key, amount)
        
        # Set expiry to end of day (if first increment)
        if new_usage == amount:
            seconds_until_midnight = (
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)
                - datetime.now(timezone.utc)
            ).seconds
            redis_client.expire(usage_key, seconds_until_midnight)
        
        # Check if approaching limit (80%)
        quotas = DAILY_QUOTAS.get(tier, DAILY_QUOTAS["free"])
        max_quota = quotas.get(resource, 0)
        
        if new_usage >= max_quota * 0.8:
            logger.warning(
                f"User {user_id} approaching quota limit: {new_usage}/{max_quota} {resource}"
            )
            
            # TODO: Send warning email/webhook
            UsageQuotaManager._send_quota_warning(user_id, tier, resource, new_usage, max_quota)
        
        # Check if exceeded
        if new_usage >= max_quota:
            logger.error(f"User {user_id} EXCEEDED quota: {new_usage}/{max_quota} {resource}")
            
            # TODO: Send limit exceeded notification
            UsageQuotaManager._send_quota_exceeded(user_id, tier, resource, new_usage, max_quota)
    
    @staticmethod
    def _send_quota_warning(user_id: str, tier: str, resource: str, usage: int, quota: int):
        """Send quota warning (80% threshold)"""
        # TODO: Integrate with email service or webhook
        logger.info(f"TODO: Send quota warning to {user_id}")
        pass
    
    @staticmethod
    def _send_quota_exceeded(user_id: str, tier: str, resource: str, usage: int, quota: int):
        """Send quota exceeded notification"""
        # TODO: Integrate with email service or webhook
        logger.info(f"TODO: Send quota exceeded to {user_id}")
        pass
    
    @staticmethod
    def get_usage_summary(user_id: str, tier: str) -> Dict:
        """Get usage summary for user"""
        if not REDIS_AVAILABLE:
            return {}
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        quotas = DAILY_QUOTAS.get(tier, DAILY_QUOTAS["free"])
        
        summary = {}
        for resource, max_quota in quotas.items():
            usage_key = f"quota:{user_id}:{resource}:{today}"
            current_usage = int(redis_client.get(usage_key) or 0)
            
            summary[resource] = {
                "quota": max_quota,
                "used": current_usage,
                "remaining": max(0, max_quota - current_usage),
                "percentage": round((current_usage / max_quota * 100) if max_quota > 0 else 0, 2)
            }
        
        return summary


# Export
__all__ = ['UsageQuotaManager', 'DAILY_QUOTAS']
Update production/api.py to enforce quotas:
pythonfrom security.usage_quotas import UsageQuotaManager

@app.post("/translate/text", tags=["Translation"])
async def translate_text_endpoint(
    request: Request,
    translation_request: TranslationRequest,
    user: dict = Depends(auth_manager.verify_request)
):
    """Translate text WITH QUOTA ENFORCEMENT"""
    
    user_id = user.get("user_id")
    tier = user.get("tier", "free")
    
    # CHECK QUOTA FIRST
    allowed, quota_info = UsageQuotaManager.check_quota(user_id, tier, "requests")
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily Quota Exceeded",
                "message": f"You've used all {quota_info['quota']} requests for today",
                "quota": quota_info,
                "upgrade_url": "https://yoursite.com/pricing"
            }
        )
    
    # ... rest of endpoint
    
    # INCREMENT USAGE AT END
    UsageQuotaManager.increment_usage(user_id, tier, "requests", 1)
    
    return result


@app.get("/usage", tags=["Usage"])
async def get_usage(
    request: Request,
    user: dict = Depends(auth_manager.verify_request)
):
    """Get current usage and quotas"""
    user_id = user.get("user_id")
    tier = user.get("tier", "free")
    
    summary = UsageQuotaManager.get_usage_summary(user_id, tier)
    
    return {
        "user_id": user_id,
        "tier": tier,
        "usage": summary,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

📝 UPDATE REQUIREMENTS
Add to production/requirements.txt:
txt# Security
bcrypt==4.1.2

# Monitoring
prometheus-client==0.19.0

# Datetime
python-dateutil==2.8.2

🎯 SUMMARY OF FIXES
Critical Security (Deploy Immediately):

✅ Pickle → JSON in cache - Eliminates RCE risk
✅ API key hashing with bcrypt - Keys never stored in plain text
✅ CORS hard-fail - Production won't start with misconfiguration

Operational Improvements:

✅ Prometheus metrics - Full observability at /metrics
✅ Graceful degradation - API starts even if models fail

Business Logic:

✅ API key rotation - Users can rotate keys securely
✅ Usage quotas enforcement - Hard limits with billing hooks

What's Still Missing (Optional):

OpenTelemetry distributed tracing (add if you have multiple services)
Stripe billing integration (add when monetizing)
Redis Sentinel/Cluster (add when scaling > 1000 users)
Message queue (RabbitMQ/SQS) - add when load requires async processing


🚀 DEPLOYMENT CHECKLIST
bash# 1. Update code with all fixes above

# 2. Install new dependencies
pip install bcrypt==4.1.2 prometheus-client==0.19.0

# 3. Set environment variables
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ALLOWED_ORIGINS="https://yourdomain.com"
export ENVIRONMENT="production"

# 4. Clear old pickled cache (IMPORTANT!)
redis-cli FLUSHDB

# 5. Restart services
docker-compose down
docker-compose up --build -d

# 6. Verify metrics endpoint
curl http://localhost:8000/metrics

# 7. Test degraded mode
# Stop Redis temporarily and verify API still starts

# 8. Test API key rotation
curl -X POST http://localhost:8000/auth/rotate-api-key \
  -H "X-API-Key: YOUR_OLD_KEY"
#!/usr/bin/env python3
"""
Authentication and Authorization System
SECURE VERSION - API keys hashed with bcrypt
Supports API keys and JWT tokens
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import jwt
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import redis
from functools import wraps
import os

# Try to import bcrypt
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("⚠️  bcrypt not installed. Install with: pip install bcrypt")

# Configuration
# Security: Generate unique key per instance if not set (logged warning)
_default_secret = secrets.token_urlsafe(32)
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = _default_secret
    print("⚠️  WARNING: JWT_SECRET_KEY not set! Using auto-generated key (will change on restart)")
    print("⚠️  Set JWT_SECRET_KEY environment variable for production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# Redis for API key storage - with graceful fallback
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    redis_client = None
    REDIS_AVAILABLE = False
    print("⚠️  Redis not available. API key storage will not work.")

# Security schemes
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
    if not BCRYPT_AVAILABLE:
        raise RuntimeError("bcrypt not installed")
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
    if not BCRYPT_AVAILABLE:
        return False
    try:
        return bcrypt.checkpw(api_key.encode(), hashed.encode())
    except Exception:
        return False


class APIKeyManager:
    """Manage API keys - SECURE VERSION with bcrypt hashing"""
    
    @staticmethod
    def generate_api_key(user_id: str, tier: str = "free") -> str:
        """
        Generate a new API key
        
        Returns the PLAIN key (user sees this once)
        Stores HASHED version in Redis
        """
        if not REDIS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Redis not available")
        
        if not BCRYPT_AVAILABLE:
            raise HTTPException(status_code=503, detail="bcrypt not available")
        
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
        """Get all key metadata for a user (NOT full keys - those are never stored)"""
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
    """Manage JWT tokens - with timezone-aware datetime"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None


class AuthManager:
    """Combined authentication manager"""
    
    @staticmethod
    async def verify_request(
        api_key: Optional[str] = Security(api_key_header),
        bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
    ) -> Dict:
        """
        Verify request using either API key or JWT token
        Returns user data if authenticated
        """
        
        # Try API key first
        if api_key:
            user_data = APIKeyManager.validate_api_key(api_key)
            if user_data:
                return user_data
        
        # Try JWT token
        if bearer:
            token = bearer.credentials
            payload = JWTManager.verify_token(token)
            if payload:
                return payload
        
        # No valid authentication
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    @staticmethod
    async def verify_admin(
        api_key: Optional[str] = Security(api_key_header),
        bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
    ) -> Dict:
        """Verify admin-level authentication"""
        user_data = await AuthManager.verify_request(api_key, bearer)
        
        if user_data.get("role") != "admin" and user_data.get("tier") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        return user_data


# Rate limiting based on tier
RATE_LIMITS = {
    "free": {"requests_per_minute": 10, "requests_per_day": 1000},
    "basic": {"requests_per_minute": 50, "requests_per_day": 10000},
    "pro": {"requests_per_minute": 200, "requests_per_day": 100000},
    "enterprise": {"requests_per_minute": 1000, "requests_per_day": 1000000},
    "admin": {"requests_per_minute": 10000, "requests_per_day": 10000000}
}


def get_rate_limit(tier: str) -> Dict:
    """Get rate limits for a tier"""
    return RATE_LIMITS.get(tier, RATE_LIMITS["free"])


# Initialize some default API keys for testing
def initialize_default_keys():
    """Initialize default API keys (ONLY FOR DEVELOPMENT)"""
    if os.getenv("ENVIRONMENT") == "development":
        # Create a test key
        test_key = APIKeyManager.generate_api_key("test_user", "pro")
        print(f"🔑 Development API Key: {test_key}")
        print("⚠️  Remove this in production!")


if __name__ == "__main__":
    initialize_default_keys()

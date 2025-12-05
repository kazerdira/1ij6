#!/usr/bin/env python3
"""
Authentication and Authorization System
Supports API keys and JWT tokens
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import jwt
from datetime import datetime, timedelta
import hashlib
import secrets
import redis
from functools import wraps
import os

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Redis for API key storage
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class APIKeyManager:
    """Manage API keys"""
    
    @staticmethod
    def generate_api_key(user_id: str, tier: str = "free") -> str:
        """Generate a new API key"""
        key = f"tr_{secrets.token_urlsafe(32)}"
        
        # Store in Redis with metadata
        key_data = {
            "user_id": user_id,
            "tier": tier,
            "created_at": datetime.now().isoformat(),
            "requests_today": 0,
            "total_requests": 0
        }
        
        redis_client.hset(f"api_key:{key}", mapping=key_data)
        redis_client.sadd(f"user_keys:{user_id}", key)
        
        return key
    
    @staticmethod
    def validate_api_key(api_key: str) -> Optional[Dict]:
        """Validate API key and return user data"""
        if not api_key or not api_key.startswith("tr_"):
            return None
        
        key_data = redis_client.hgetall(f"api_key:{api_key}")
        
        if not key_data:
            return None
        
        # Increment usage counter
        redis_client.hincrby(f"api_key:{api_key}", "requests_today", 1)
        redis_client.hincrby(f"api_key:{api_key}", "total_requests", 1)
        
        return key_data
    
    @staticmethod
    def revoke_api_key(api_key: str) -> bool:
        """Revoke an API key"""
        key_data = redis_client.hgetall(f"api_key:{api_key}")
        
        if not key_data:
            return False
        
        user_id = key_data.get("user_id")
        
        redis_client.delete(f"api_key:{api_key}")
        redis_client.srem(f"user_keys:{user_id}", api_key)
        
        return True
    
    @staticmethod
    def get_user_keys(user_id: str) -> list:
        """Get all keys for a user"""
        return list(redis_client.smembers(f"user_keys:{user_id}"))


class JWTManager:
    """Manage JWT tokens"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
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
        except jwt.JWTError:
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

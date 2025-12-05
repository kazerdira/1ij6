#!/usr/bin/env python3
"""
Rate Limiter with Redis Backend
Implements sliding window algorithm for accurate rate limiting
"""

from fastapi import HTTPException, status, Request
from typing import Optional, Tuple
import redis
import time
from datetime import datetime, timedelta
import hashlib
import os

# Redis connection with graceful fallback
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


class RateLimiter:
    """Advanced rate limiter using Redis"""
    
    def __init__(self):
        self.redis = redis_client
        self.enabled = REDIS_AVAILABLE
    
    def _get_identifier(self, request: Request, user_data: dict) -> str:
        """Get unique identifier for rate limiting"""
        # Prefer API key, fallback to IP
        if user_data:
            return f"user:{user_data.get('user_id', 'unknown')}"
        
        # Get client IP (handle proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def check_rate_limit(
        self,
        request: Request,
        user_data: Optional[dict] = None,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit
        
        Returns:
            (allowed, info_dict)
        """
        if not self.enabled:
            # No rate limiting if Redis unavailable
            return True, {"limit": max_requests, "remaining": max_requests, "reset": 0, "current": 0}
            
        identifier = self._get_identifier(request, user_data)
        key = f"rate_limit:{identifier}:{window_seconds}"
        
        now = time.time()
        window_start = now - window_seconds
        
        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry
        pipe.expire(key, window_seconds * 2)
        
        results = pipe.execute()
        current_requests = results[1]
        
        allowed = current_requests < max_requests
        
        info = {
            "limit": max_requests,
            "remaining": max(0, max_requests - current_requests - 1),
            "reset": int(now + window_seconds),
            "current": current_requests
        }
        
        return allowed, info
    
    def check_daily_limit(
        self,
        request: Request,
        user_data: Optional[dict] = None,
        max_requests: int = 10000
    ) -> Tuple[bool, dict]:
        """Check daily rate limit"""
        if not self.enabled:
            return True, {"limit": max_requests, "remaining": max_requests, "reset_date": "", "current": 0}
            
        identifier = self._get_identifier(request, user_data)
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"daily_limit:{identifier}:{today}"
        
        current_count = self.redis.incr(key)
        
        if current_count == 1:
            # Set expiry to end of day
            seconds_until_midnight = (
                datetime.combine(datetime.now().date() + timedelta(days=1), datetime.min.time()) 
                - datetime.now()
            ).seconds
            self.redis.expire(key, seconds_until_midnight)
        
        allowed = current_count <= max_requests
        
        info = {
            "limit": max_requests,
            "remaining": max(0, max_requests - current_count),
            "reset_date": today,
            "current": current_count
        }
        
        return allowed, info
    
    def check_endpoint_limit(
        self,
        request: Request,
        endpoint: str,
        user_data: Optional[dict] = None,
        max_requests: int = 10,
        window_seconds: int = 60
    ) -> Tuple[bool, dict]:
        """Check rate limit per endpoint"""
        if not self.enabled:
            return True, {"endpoint": endpoint, "limit": max_requests, "remaining": max_requests, "reset": 0}
            
        identifier = self._get_identifier(request, user_data)
        key = f"endpoint_limit:{identifier}:{endpoint}:{window_seconds}"
        
        now = time.time()
        window_start = now - window_seconds
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds * 2)
        
        results = pipe.execute()
        current_requests = results[1]
        
        allowed = current_requests < max_requests
        
        info = {
            "endpoint": endpoint,
            "limit": max_requests,
            "remaining": max(0, max_requests - current_requests - 1),
            "reset": int(now + window_seconds)
        }
        
        return allowed, info


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on system load
    """
    
    def __init__(self):
        super().__init__()
        self.base_limits = {
            "free": 10,
            "basic": 50,
            "pro": 200,
            "enterprise": 1000
        }
    
    def get_system_load(self) -> float:
        """Get current system load (0.0 to 1.0)"""
        if not self.enabled:
            return 0.0
        # Check Redis for current active requests
        active_requests = int(self.redis.get("active_requests") or 0)
        max_capacity = 100  # Configure based on your system
        
        return min(active_requests / max_capacity, 1.0)
    
    def get_adaptive_limit(self, tier: str) -> int:
        """Get rate limit adjusted for system load"""
        base_limit = self.base_limits.get(tier, 10)
        load = self.get_system_load()
        
        # Reduce limits under high load
        if load > 0.9:
            multiplier = 0.25
        elif load > 0.75:
            multiplier = 0.5
        elif load > 0.5:
            multiplier = 0.75
        else:
            multiplier = 1.0
        
        return int(base_limit * multiplier)


def rate_limit_middleware(
    max_requests: int = 60,
    window_seconds: int = 60
):
    """
    Decorator for rate limiting endpoints
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            limiter = RateLimiter()
            
            # Get user data from request state (set by auth middleware)
            user_data = getattr(request.state, "user", None)
            
            # Check rate limit
            allowed, info = limiter.check_rate_limit(
                request, user_data, max_requests, window_seconds
            )
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": info["limit"],
                        "remaining": info["remaining"],
                        "reset": info["reset"]
                    },
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(window_seconds)
                    }
                )
            
            # Add rate limit headers to response
            response = await func(request, *args, **kwargs)
            
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(info["reset"])
            
            return response
        
        return wrapper
    return decorator

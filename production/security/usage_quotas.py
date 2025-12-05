#!/usr/bin/env python3
"""
Usage Quotas Enforcement
Hard limits on daily usage with billing integration hooks
"""

from typing import Dict, Tuple
import os
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis
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
    },
    "admin": {
        "requests": 10000000,
        "compute_seconds": 3000000,
        "audio_minutes": 100000
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
        
        # Calculate reset time (midnight UTC)
        tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        info = {
            "resource": resource,
            "quota": max_quota,
            "used": current_usage,
            "remaining": remaining,
            "reset_at": tomorrow.isoformat()
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
        
        # Set expiry to end of day + buffer (if first increment)
        if new_usage == amount:
            # Expire at midnight UTC + 1 hour buffer
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1, hours=1)
            seconds_until_expiry = int((tomorrow - datetime.now(timezone.utc)).total_seconds())
            redis_client.expire(usage_key, seconds_until_expiry)
        
        # Check if approaching limit (80%)
        quotas = DAILY_QUOTAS.get(tier, DAILY_QUOTAS["free"])
        max_quota = quotas.get(resource, 0)
        
        if max_quota > 0:
            if new_usage >= max_quota * 0.8 and new_usage < max_quota:
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
        # Example: send_email(user_id, f"You've used {usage}/{quota} {resource}")
        pass
    
    @staticmethod
    def _send_quota_exceeded(user_id: str, tier: str, resource: str, usage: int, quota: int):
        """Send quota exceeded notification"""
        # TODO: Integrate with email service or webhook
        # Example: send_email(user_id, f"Quota exceeded for {resource}")
        pass
    
    @staticmethod
    def get_usage_summary(user_id: str, tier: str) -> Dict:
        """Get usage summary for user"""
        if not REDIS_AVAILABLE:
            return {"error": "Redis not available"}
        
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

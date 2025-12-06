#!/usr/bin/env python3
"""
RAILWAY DEPLOYMENT FIX - api.py Startup Patch
==============================================

Add this code to api.py BEFORE the app initialization.
This fixes critical Railway deployment issues.

INTEGRATION INSTRUCTIONS:
1. Find the imports section in api.py
2. Add the Redis URL parser code after imports
3. Call configure_redis_from_railway() before creating the app
4. Update the uvicorn.run() call to use get_railway_port()
"""

import os
from urllib.parse import urlparse
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CRITICAL FIX #1: Parse Railway's REDIS_URL
# =============================================================================
def configure_redis_from_railway():
    """
    Railway provides Redis connection as: redis://user:pass@host:port
    Our app expects separate REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
    
    This function parses REDIS_URL and sets individual env vars.
    """
    redis_url = os.getenv("REDIS_URL")
    
    # Only parse if REDIS_URL exists and REDIS_HOST is not already set
    if redis_url and not os.getenv("REDIS_HOST"):
        try:
            parsed = urlparse(redis_url)
            
            # Extract components
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            password = parsed.password
            
            # Set environment variables
            os.environ["REDIS_HOST"] = host
            os.environ["REDIS_PORT"] = str(port)
            
            if password:
                os.environ["REDIS_PASSWORD"] = password
            
            logger.info(f"✅ Configured Redis from REDIS_URL: {host}:{port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to parse REDIS_URL: {e}")
            logger.warning("⚠️  Redis connection may fail!")


# =============================================================================
# CRITICAL FIX #2: Read Railway's PORT variable
# =============================================================================
def get_railway_port():
    """
    Railway sets the PORT environment variable dynamically.
    This function reads it safely with fallback to 8000.
    """
    try:
        port = int(os.getenv("PORT", 8000))
        logger.info(f"🚂 Using Railway PORT: {port}")
        return port
    except ValueError:
        logger.warning("⚠️  Invalid PORT value, using default 8000")
        return 8000


# =============================================================================
# FIX #3: Log Railway environment for debugging
# =============================================================================
def log_railway_environment():
    """
    Log Railway-specific environment variables for debugging.
    Helps troubleshoot deployment issues.
    """
    is_railway = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME")
    
    if not is_railway:
        return  # Not on Railway
    
    logger.info("=" * 70)
    logger.info("🚂 RAILWAY DEPLOYMENT ENVIRONMENT")
    logger.info("=" * 70)
    
    railway_vars = {
        "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
        "RAILWAY_SERVICE_NAME": os.getenv("RAILWAY_SERVICE_NAME"),
        "RAILWAY_DEPLOYMENT_ID": os.getenv("RAILWAY_DEPLOYMENT_ID"),
        "PORT": os.getenv("PORT"),
        "REDIS_URL": "***" if os.getenv("REDIS_URL") else None,
        "REDIS_HOST": os.getenv("REDIS_HOST"),
        "REDIS_PORT": os.getenv("REDIS_PORT"),
        "ENVIRONMENT": os.getenv("ENVIRONMENT"),
        "WHISPER_MODEL": os.getenv("WHISPER_MODEL"),
        "MAX_WORKERS": os.getenv("MAX_WORKERS"),
    }
    
    for key, value in railway_vars.items():
        if value:
            logger.info(f"  {key}: {value}")
    
    logger.info("=" * 70)


# =============================================================================
# FIX #4: Validate critical environment variables
# =============================================================================
def validate_production_config():
    """
    Validate critical configuration for production.
    Prevents deployment with insecure defaults.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment != "production":
        logger.warning(f"⚠️  Running in {environment} mode")
        return  # Only validate in production
    
    issues = []
    
    # Check JWT secret
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret or jwt_secret in ["change-me", "CHANGE_ME_generate_a_real_secret_key"]:
        issues.append("JWT_SECRET_KEY not set or using default value")
    
    # Check CORS
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
    if allowed_origins == "*":
        issues.append("ALLOWED_ORIGINS set to '*' (allows all origins)")
    
    # Check Redis
    if not os.getenv("REDIS_HOST") and not os.getenv("REDIS_URL"):
        issues.append("Neither REDIS_HOST nor REDIS_URL is set (caching disabled)")
    
    # Log warnings
    if issues:
        logger.warning("=" * 70)
        logger.warning("⚠️  PRODUCTION CONFIGURATION WARNINGS")
        logger.warning("=" * 70)
        for issue in issues:
            logger.warning(f"  • {issue}")
        logger.warning("=" * 70)


# =============================================================================
# INTEGRATION CODE
# =============================================================================
"""
Add this to your api.py file:

1. After imports section, add:

    from urllib.parse import urlparse
    
    # Railway deployment fixes
    configure_redis_from_railway()
    log_railway_environment()
    validate_production_config()

2. In the startup event, add:

    @app.on_event("startup")
    async def startup_event():
        # ... existing code ...
        
        # Validate configuration
        validate_production_config()

3. Update the main block:

    if __name__ == "__main__":
        port = get_railway_port()
        
        uvicorn.run(
            "api:app",
            host="0.0.0.0",
            port=port,  # Use Railway's port
            reload=False,
            log_level="info",
            access_log=True
        )
"""


# =============================================================================
# QUICK INTEGRATION - Copy-Paste This Entire Block
# =============================================================================
"""
# Railway Deployment Fixes
import os
from urllib.parse import urlparse

def configure_redis_from_railway():
    redis_url = os.getenv("REDIS_URL")
    if redis_url and not os.getenv("REDIS_HOST"):
        try:
            parsed = urlparse(redis_url)
            os.environ["REDIS_HOST"] = parsed.hostname or "localhost"
            os.environ["REDIS_PORT"] = str(parsed.port or 6379)
            if parsed.password:
                os.environ["REDIS_PASSWORD"] = parsed.password
            logger.info(f"✅ Configured Redis from REDIS_URL")
        except Exception as e:
            logger.error(f"❌ Failed to parse REDIS_URL: {e}")

# Call immediately
configure_redis_from_railway()
"""

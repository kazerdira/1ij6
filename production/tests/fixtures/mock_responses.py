#!/usr/bin/env python3
"""
Test Fixtures: Mock Responses
=============================

Provides mock response data for testing API interactions.
"""

from datetime import datetime
from typing import Dict, Any


# =============================================================================
# TRANSLATION RESPONSES
# =============================================================================

TRANSLATION_SUCCESS = {
    "original": "Hello, world!",
    "translated": "Bonjour, le monde!",
    "source_language": "eng_Latn",
    "target_language": "fra_Latn",
    "cached": False,
    "request_id": "test-request-123",
    "timestamp": "2025-01-01T12:00:00"
}

TRANSLATION_CACHED = {
    **TRANSLATION_SUCCESS,
    "cached": True
}

TRANSLATION_ERROR = {
    "error": "Translation failed",
    "request_id": "test-request-456",
    "timestamp": "2025-01-01T12:00:00"
}


# =============================================================================
# TRANSCRIPTION RESPONSES
# =============================================================================

TRANSCRIPTION_SUCCESS = {
    "original": "안녕하세요",
    "translated": "Hello",
    "source_language": "ko",
    "target_language": "eng_Latn",
    "cached": False,
    "request_id": "test-request-789",
    "timestamp": "2025-01-01T12:00:00"
}


# =============================================================================
# HEALTH CHECK RESPONSES
# =============================================================================

HEALTH_OK = {
    "status": "healthy",
    "checks": {
        "system": {"status": "ok", "cpu_percent": 25.0, "memory_percent": 50.0},
        "models": {"status": "ok", "whisper_loaded": True, "nllb_loaded": True},
        "redis": {"status": "ok", "connected": True}
    },
    "timestamp": "2025-01-01T12:00:00"
}

HEALTH_DEGRADED = {
    "status": "degraded",
    "checks": {
        "system": {"status": "ok"},
        "models": {"status": "ok"},
        "redis": {"status": "error", "connected": False, "error": "Connection refused"}
    },
    "timestamp": "2025-01-01T12:00:00"
}


# =============================================================================
# METRICS RESPONSES
# =============================================================================

METRICS_RESPONSE = {
    "translator": {
        "total_requests": 1000,
        "active_requests": 5,
        "max_concurrent_requests": 20,
        "failed_requests": 10,
        "success_rate": 99.0,
        "device": "cuda",
        "models_loaded": True
    },
    "cache": {
        "hits": 500,
        "misses": 200,
        "sets": 300,
        "hit_rate": 71.4,
        "enabled": True
    },
    "circuit_breakers": {
        "whisper_transcribe": {"state": "closed", "failure_count": 0},
        "nllb_translate": {"state": "closed", "failure_count": 0}
    },
    "rate_limiting": {
        "enabled": True
    },
    "timestamp": "2025-01-01T12:00:00"
}


# =============================================================================
# API KEY RESPONSES
# =============================================================================

API_KEY_CREATED = {
    "api_key": "tr_test_generated_key_12345",
    "user_id": "test_user",
    "tier": "pro",
    "rate_limits": {
        "requests_per_minute": 200,
        "requests_per_day": 100000
    },
    "created_at": "2025-01-01T12:00:00"
}

DEV_API_KEY_CREATED = {
    **API_KEY_CREATED,
    "warning": "⚠️ This is a DEVELOPMENT key. Do not use in production!",
    "usage": 'curl -H "X-API-Key: tr_test_generated_key_12345" http://localhost:8000/translate/text'
}


# =============================================================================
# ERROR RESPONSES
# =============================================================================

ERROR_UNAUTHORIZED = {
    "error": "Unauthorized",
    "message": "Invalid or missing API key",
    "request_id": "test-request-error-1",
    "timestamp": "2025-01-01T12:00:00"
}

ERROR_RATE_LIMITED = {
    "error": "Rate limit exceeded",
    "limit": 60,
    "remaining": 0,
    "reset": 1704110400,  # Unix timestamp
    "request_id": "test-request-error-2"
}

ERROR_SERVICE_UNAVAILABLE = {
    "error": "Service Temporarily Unavailable",
    "message": "The service is experiencing high error rates. Please try again later.",
    "request_id": "test-request-error-3",
    "retry_after": 60
}

ERROR_VALIDATION = {
    "detail": [
        {
            "loc": ["body", "text"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}


# =============================================================================
# USER DATA
# =============================================================================

USER_FREE = {
    "user_id": "user_free_001",
    "tier": "free",
    "created_at": "2025-01-01T00:00:00",
    "requests_today": 50,
    "total_requests": 500
}

USER_PRO = {
    "user_id": "user_pro_001",
    "tier": "pro",
    "created_at": "2025-01-01T00:00:00",
    "requests_today": 500,
    "total_requests": 50000
}

USER_ENTERPRISE = {
    "user_id": "user_enterprise_001",
    "tier": "enterprise",
    "created_at": "2025-01-01T00:00:00",
    "requests_today": 5000,
    "total_requests": 500000
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_translation_response(
    original: str,
    translated: str,
    source_lang: str = "eng_Latn",
    target_lang: str = "fra_Latn",
    cached: bool = False
) -> Dict[str, Any]:
    """Create a custom translation response"""
    return {
        "original": original,
        "translated": translated,
        "source_language": source_lang,
        "target_language": target_lang,
        "cached": cached,
        "request_id": f"req-{datetime.now().timestamp()}",
        "timestamp": datetime.now().isoformat()
    }


def create_error_response(
    error: str,
    message: str,
    status_code: int = 500
) -> Dict[str, Any]:
    """Create a custom error response"""
    return {
        "error": error,
        "message": message,
        "status_code": status_code,
        "request_id": f"err-{datetime.now().timestamp()}",
        "timestamp": datetime.now().isoformat()
    }

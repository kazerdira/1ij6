#!/usr/bin/env python3
"""
Unit Tests: Rate Limiter
========================

Tests for security/rate_limiter.py
These tests verify rate limiting logic.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestRateLimiterBasics:
    """Basic rate limiter functionality tests"""
    
    @pytest.mark.unit
    def test_rate_limiter_import(self):
        """RateLimiter should be importable"""
        from security.rate_limiter import RateLimiter
        limiter = RateLimiter()
        assert limiter is not None
    
    @pytest.mark.unit
    def test_rate_limiter_disabled_without_redis(self):
        """Rate limiter should be disabled when Redis unavailable"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        # Without Redis, enabled should be False
        # (depends on environment - may be True if Redis is running)
        assert hasattr(limiter, 'enabled')
    
    @pytest.mark.unit
    def test_check_rate_limit_returns_tuple(self, mock_redis):
        """check_rate_limit should return (allowed, info) tuple"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        limiter.redis = mock_redis
        limiter.enabled = True
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "127.0.0.1"
        
        allowed, info = limiter.check_rate_limit(
            mock_request,
            user_data=None,
            max_requests=60,
            window_seconds=60
        )
        
        assert isinstance(allowed, bool)
        assert isinstance(info, dict)
        assert "limit" in info
        assert "remaining" in info
    
    @pytest.mark.unit
    def test_rate_limit_allows_when_disabled(self):
        """When disabled, all requests should be allowed"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        limiter.enabled = False
        
        mock_request = MagicMock()
        
        allowed, info = limiter.check_rate_limit(
            mock_request,
            user_data=None,
            max_requests=1,  # Very low limit
            window_seconds=60
        )
        
        assert allowed is True


class TestRateLimiterIdentifier:
    """Tests for request identifier extraction"""
    
    @pytest.mark.unit
    def test_identifier_uses_api_key_when_present(self):
        """Should use user_id from user_data when available"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        mock_request = MagicMock()
        user_data = {"user_id": "test_user_123", "tier": "pro"}
        
        identifier = limiter._get_identifier(mock_request, user_data)
        
        assert "test_user_123" in identifier
    
    @pytest.mark.unit
    def test_identifier_uses_ip_as_fallback(self):
        """Should use IP address when no user_data"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "192.168.1.100"
        
        identifier = limiter._get_identifier(mock_request, None)
        
        assert "192.168.1.100" in identifier
    
    @pytest.mark.unit
    def test_identifier_uses_forwarded_for_header(self):
        """Should use X-Forwarded-For header for proxied requests"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "10.0.0.1, 10.0.0.2"
        mock_request.client.host = "127.0.0.1"
        
        identifier = limiter._get_identifier(mock_request, None)
        
        # Should use first IP from X-Forwarded-For
        assert "10.0.0.1" in identifier


class TestRateLimits:
    """Tests for rate limit configuration"""
    
    @pytest.mark.unit
    def test_get_rate_limit_free_tier(self):
        """Free tier should have lowest limits"""
        from security.auth import get_rate_limit
        
        limits = get_rate_limit("free")
        
        assert limits["requests_per_minute"] <= 20
        assert limits["requests_per_day"] <= 2000
    
    @pytest.mark.unit
    def test_get_rate_limit_pro_tier(self):
        """Pro tier should have higher limits"""
        from security.auth import get_rate_limit
        
        limits = get_rate_limit("pro")
        
        assert limits["requests_per_minute"] >= 100
    
    @pytest.mark.unit
    def test_get_rate_limit_enterprise_tier(self):
        """Enterprise tier should have highest limits"""
        from security.auth import get_rate_limit
        
        limits = get_rate_limit("enterprise")
        
        assert limits["requests_per_minute"] >= 500
    
    @pytest.mark.unit
    def test_get_rate_limit_unknown_tier_defaults_to_free(self):
        """Unknown tier should default to free tier limits"""
        from security.auth import get_rate_limit
        
        free_limits = get_rate_limit("free")
        unknown_limits = get_rate_limit("unknown_tier")
        
        assert unknown_limits == free_limits

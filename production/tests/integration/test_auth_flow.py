#!/usr/bin/env python3
"""
Integration Tests: Authentication Flow
======================================

Tests for complete authentication workflows.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestAPIKeyAuthentication:
    """Tests for API key authentication flow"""
    
    @pytest.mark.integration
    def test_api_key_format(self):
        """API keys should have correct format"""
        from security.auth import APIKeyManager
        
        # Valid key format: tr_<random>
        valid_key = "tr_abc123xyz456"
        invalid_key = "abc123xyz456"
        
        assert valid_key.startswith("tr_")
        assert not invalid_key.startswith("tr_")
    
    @pytest.mark.integration
    def test_api_key_validation_rejects_invalid(self):
        """Invalid API keys should be rejected"""
        from security.auth import APIKeyManager
        
        result = APIKeyManager.validate_api_key("invalid_key")
        assert result is None
    
    @pytest.mark.integration
    def test_api_key_validation_rejects_empty(self):
        """Empty API keys should be rejected"""
        from security.auth import APIKeyManager
        
        result = APIKeyManager.validate_api_key("")
        assert result is None
    
    @pytest.mark.integration
    def test_api_key_validation_rejects_none(self):
        """None API keys should be rejected"""
        from security.auth import APIKeyManager
        
        result = APIKeyManager.validate_api_key(None)
        assert result is None


class TestJWTAuthentication:
    """Tests for JWT token authentication"""
    
    @pytest.mark.integration
    def test_jwt_token_creation(self):
        """JWT tokens should be creatable"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        
        # Create token
        token = manager.create_access_token(
            data={"user_id": "test_user", "tier": "pro"}
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
    
    @pytest.mark.integration
    def test_jwt_token_has_three_parts(self):
        """JWT tokens should have header.payload.signature format"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        token = manager.create_access_token(data={"user_id": "test"})
        
        parts = token.split(".")
        assert len(parts) == 3
    
    @pytest.mark.integration
    def test_jwt_token_decoding(self):
        """JWT tokens should be decodable"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        
        original_data = {"user_id": "test_user_123", "tier": "enterprise"}
        token = manager.create_access_token(data=original_data)
        
        # Decode
        decoded = manager.decode_access_token(token)
        
        assert decoded is not None
        assert decoded.get("user_id") == "test_user_123"
        assert decoded.get("tier") == "enterprise"
    
    @pytest.mark.integration
    def test_jwt_invalid_token_rejected(self):
        """Invalid JWT tokens should be rejected"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        
        result = manager.decode_access_token("invalid.token.here")
        assert result is None
    
    @pytest.mark.integration
    def test_jwt_tampered_token_rejected(self):
        """Tampered JWT tokens should be rejected"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        
        token = manager.create_access_token(data={"user_id": "test"})
        
        # Tamper with token
        tampered = token[:-5] + "XXXXX"
        
        result = manager.decode_access_token(tampered)
        assert result is None


class TestTierBasedLimits:
    """Tests for tier-based rate limits"""
    
    @pytest.mark.integration
    @pytest.mark.parametrize("tier,min_rpm", [
        ("free", 5),
        ("basic", 30),
        ("pro", 100),
        ("enterprise", 500),
    ])
    def test_tier_limits(self, tier, min_rpm):
        """Each tier should have appropriate limits"""
        from security.auth import get_rate_limit
        
        limits = get_rate_limit(tier)
        
        assert limits["requests_per_minute"] >= min_rpm
    
    @pytest.mark.integration
    def test_tier_limits_increase_with_tier(self):
        """Higher tiers should have higher limits"""
        from security.auth import get_rate_limit
        
        free = get_rate_limit("free")
        basic = get_rate_limit("basic")
        pro = get_rate_limit("pro")
        enterprise = get_rate_limit("enterprise")
        
        assert free["requests_per_minute"] < basic["requests_per_minute"]
        assert basic["requests_per_minute"] < pro["requests_per_minute"]
        assert pro["requests_per_minute"] < enterprise["requests_per_minute"]


class TestAuthManager:
    """Tests for AuthManager class"""
    
    @pytest.mark.integration
    def test_auth_manager_instantiation(self):
        """AuthManager should instantiate correctly"""
        from security.auth import AuthManager
        
        manager = AuthManager()
        
        assert manager is not None
        assert hasattr(manager, 'verify_request')
        assert hasattr(manager, 'create_access_token')

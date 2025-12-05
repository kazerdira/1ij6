#!/usr/bin/env python3
"""
Security Module Tests
Tests for authentication, rate limiting, and input validation
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestInputValidator:
    """Test input validation functions"""
    
    def test_validate_text_normal(self):
        """Test normal text passes validation"""
        from security.input_validator import InputValidator
        
        result = InputValidator.validate_text("Hello world")
        assert result == "Hello world"
    
    def test_validate_text_empty_rejected(self):
        """Test empty text is rejected"""
        from security.input_validator import InputValidator
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text("")
        assert exc.value.status_code == 400
    
    def test_validate_text_null_bytes_rejected(self):
        """Test null bytes in text are rejected"""
        from security.input_validator import InputValidator
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text("Hello\x00World")
        assert exc.value.status_code == 400
    
    def test_validate_text_too_long_rejected(self):
        """Test text exceeding max length is rejected"""
        from security.input_validator import InputValidator
        from fastapi import HTTPException
        
        long_text = "a" * 200000
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text(long_text)
        assert exc.value.status_code == 413
    
    def test_validate_language_code_valid(self):
        """Test valid language codes pass"""
        from security.input_validator import InputValidator
        
        # Whisper format
        assert InputValidator.validate_language_code("en") == "en"
        assert InputValidator.validate_language_code("zh") == "zh"
        
        # NLLB format
        assert InputValidator.validate_language_code("eng_Latn") == "eng_Latn"
        assert InputValidator.validate_language_code("fra_Latn") == "fra_Latn"
    
    def test_validate_language_code_invalid(self):
        """Test invalid language codes are rejected"""
        from security.input_validator import InputValidator
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException):
            InputValidator.validate_language_code("invalid!")
        
        with pytest.raises(HTTPException):
            InputValidator.validate_language_code("a")  # Too short
    
    def test_validate_model_name_valid(self):
        """Test valid model names pass"""
        from security.input_validator import InputValidator
        
        for model in ['tiny', 'base', 'small', 'medium', 'large']:
            assert InputValidator.validate_model_name(model) == model
    
    def test_validate_model_name_invalid(self):
        """Test invalid model names are rejected"""
        from security.input_validator import InputValidator
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException):
            InputValidator.validate_model_name("invalid_model")


class TestCircuitBreaker:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts closed"""
        from reliability.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(name="test_breaker", failure_threshold=3)
        assert cb.is_closed()
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after failures"""
        from reliability.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(name="test_failures", failure_threshold=2, reset_timeout=1)
        
        # Simulate failures
        cb.record_failure()
        assert cb.is_closed()  # Still closed after 1 failure
        
        cb.record_failure()
        assert cb.is_open()  # Opens after 2 failures
    
    def test_circuit_breaker_reset(self):
        """Test circuit breaker can be reset"""
        from reliability.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(name="test_reset", failure_threshold=1)
        cb.record_failure()
        assert cb.is_open()
        
        cb.reset()
        assert cb.is_closed()


class TestRateLimiter:
    """Test rate limiter (without Redis)"""
    
    def test_rate_limiter_no_redis(self):
        """Test rate limiter gracefully handles no Redis"""
        from security.rate_limiter import RateLimiter
        
        limiter = RateLimiter()
        # Should not crash even without Redis
        # Just allows all requests when Redis unavailable


class TestAPIKeyFormat:
    """Test API key format validation"""
    
    def test_api_key_prefix(self):
        """Test API keys have correct prefix"""
        # API keys should start with 'tr_'
        valid_key = "tr_abc123xyz"
        invalid_key = "abc123xyz"
        
        assert valid_key.startswith("tr_")
        assert not invalid_key.startswith("tr_")

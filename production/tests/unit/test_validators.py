#!/usr/bin/env python3
"""
Unit Tests: Input Validators
============================

Tests for security/input_validator.py
These tests verify input sanitization and validation logic.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import HTTPException
from security.input_validator import InputValidator


class TestTextValidation:
    """Tests for text input validation"""
    
    @pytest.mark.unit
    def test_validate_text_normal(self):
        """Normal text should pass validation unchanged"""
        result = InputValidator.validate_text("Hello world")
        assert result == "Hello world"
    
    @pytest.mark.unit
    def test_validate_text_with_whitespace(self):
        """Text should be stripped of leading/trailing whitespace"""
        result = InputValidator.validate_text("  Hello world  ")
        assert result == "Hello world"
    
    @pytest.mark.unit
    def test_validate_text_empty_rejected(self):
        """Empty text should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text("")
        assert exc.value.status_code == 400
    
    @pytest.mark.unit
    def test_validate_text_none_rejected(self):
        """None should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text(None)
        assert exc.value.status_code == 400
    
    @pytest.mark.unit
    def test_validate_text_null_bytes_rejected(self):
        """Text with null bytes should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text("Hello\x00World")
        assert exc.value.status_code == 400
        assert "null bytes" in str(exc.value.detail).lower()
    
    @pytest.mark.unit
    def test_validate_text_too_long_rejected(self):
        """Text exceeding max length should raise 413 error"""
        long_text = "a" * 200000  # Exceed 100k limit
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_text(long_text)
        assert exc.value.status_code == 413
    
    @pytest.mark.unit
    def test_validate_text_unicode_allowed(self):
        """Unicode characters should be allowed"""
        result = InputValidator.validate_text("안녕하세요 こんにちは 你好")
        assert result == "안녕하세요 こんにちは 你好"
    
    @pytest.mark.unit
    def test_validate_text_newlines_preserved(self):
        """Newlines should be preserved"""
        result = InputValidator.validate_text("Line 1\nLine 2\nLine 3")
        assert "\n" in result


class TestLanguageCodeValidation:
    """Tests for language code validation"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("code", ["en", "ko", "zh", "fr", "de"])
    def test_validate_whisper_codes(self, code):
        """Valid Whisper language codes (2 letters)"""
        result = InputValidator.validate_language_code(code)
        assert result == code
    
    @pytest.mark.unit
    @pytest.mark.parametrize("code", ["eng_Latn", "fra_Latn", "kor_Hang", "zho_Hans", "ara_Arab"])
    def test_validate_nllb_codes(self, code):
        """Valid NLLB language codes (xxx_Xxxx format)"""
        result = InputValidator.validate_language_code(code)
        assert result == code
    
    @pytest.mark.unit
    def test_validate_language_code_empty_rejected(self):
        """Empty language code should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_language_code("")
        assert exc.value.status_code == 400
    
    @pytest.mark.unit
    @pytest.mark.parametrize("code", ["e", "english", "123", "en-US", "eng-Latn"])
    def test_validate_language_code_invalid_format(self, code):
        """Invalid language code formats should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_language_code(code)
        assert exc.value.status_code == 400


class TestModelNameValidation:
    """Tests for Whisper model name validation"""
    
    @pytest.mark.unit
    @pytest.mark.parametrize("model", ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"])
    def test_validate_valid_models(self, model):
        """Valid model names should pass"""
        result = InputValidator.validate_model_name(model)
        assert result == model
    
    @pytest.mark.unit
    @pytest.mark.parametrize("model", ["invalid", "huge", "xlarge", "tiny-v2", ""])
    def test_validate_invalid_models(self, model):
        """Invalid model names should raise 400 error"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_model_name(model)
        assert exc.value.status_code == 400

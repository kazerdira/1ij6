#!/usr/bin/env python3
"""
API Endpoint Tests
Tests for all REST API endpoints
"""

import pytest


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_root_endpoint(self, api_client):
        """Test root endpoint returns welcome message"""
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_health_simple(self, api_client):
        """Test simple health check"""
        response = api_client.get("/health/simple")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_health_detailed(self, api_client):
        """Test detailed health check"""
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestLanguagesEndpoint:
    """Test language configuration endpoint"""
    
    def test_get_languages(self, api_client):
        """Test getting supported languages"""
        response = api_client.get("/languages")
        assert response.status_code == 200
        data = response.json()
        assert "whisper_languages" in data
        assert "nllb_languages" in data
        assert "en" in data["whisper_languages"]
        assert "eng_Latn" in data["nllb_languages"]


class TestTranslationEndpoint:
    """Test translation endpoint"""
    
    def test_translate_without_auth(self, api_client):
        """Test translation requires authentication"""
        response = api_client.post("/translate/text", json={
            "text": "Hello world",
            "source_lang": "eng_Latn",
            "target_lang": "fra_Latn"
        })
        # Should fail without API key (401 or 403)
        assert response.status_code in [401, 403, 422]
    
    def test_translate_invalid_language(self, api_client):
        """Test translation with invalid language code"""
        response = api_client.post(
            "/translate/text",
            json={
                "text": "Hello",
                "source_lang": "invalid_lang",
                "target_lang": "fra_Latn"
            },
            headers={"X-API-Key": "tr_test_key"}
        )
        # Should fail validation
        assert response.status_code in [400, 401, 403, 422]


class TestInputValidation:
    """Test input validation"""
    
    def test_empty_text_rejected(self, api_client):
        """Test that empty text is rejected"""
        response = api_client.post(
            "/translate/text",
            json={
                "text": "",
                "source_lang": "eng_Latn",
                "target_lang": "fra_Latn"
            },
            headers={"X-API-Key": "tr_test_key"}
        )
        assert response.status_code in [400, 401, 403, 422]
    
    def test_text_too_long_rejected(self, api_client):
        """Test that very long text is rejected"""
        long_text = "a" * 200000  # Exceed 100k limit
        response = api_client.post(
            "/translate/text",
            json={
                "text": long_text,
                "source_lang": "eng_Latn",
                "target_lang": "fra_Latn"
            },
            headers={"X-API-Key": "tr_test_key"}
        )
        assert response.status_code in [400, 401, 403, 413, 422]


class TestMetricsEndpoint:
    """Test metrics endpoint"""
    
    def test_metrics_endpoint(self, api_client):
        """Test metrics endpoint exists"""
        response = api_client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "uptime" in data or "requests" in data or "cache" in data


class TestOpenAPISchema:
    """Test OpenAPI documentation"""
    
    def test_openapi_available(self, api_client):
        """Test OpenAPI schema is accessible"""
        response = api_client.get("/v1/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
    
    def test_docs_available(self, api_client):
        """Test Swagger docs accessible"""
        response = api_client.get("/docs")
        assert response.status_code == 200

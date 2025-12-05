#!/usr/bin/env python3
"""
Integration Tests: API Endpoints
================================

Tests for api.py endpoints
These tests use TestClient to make real HTTP requests.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    @pytest.mark.integration
    def test_root_endpoint(self, api_client):
        """GET / should return welcome message"""
        response = api_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "features" in data
    
    @pytest.mark.integration
    def test_health_simple(self, api_client):
        """GET /health/simple should return OK"""
        response = api_client.get("/health/simple")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ok", "healthy"]
    
    @pytest.mark.integration
    def test_health_detailed(self, api_client):
        """GET /health should return detailed status"""
        response = api_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestMetricsEndpoint:
    """Tests for metrics endpoint"""
    
    @pytest.mark.integration
    def test_metrics_returns_data(self, api_client):
        """GET /metrics should return metrics data"""
        response = api_client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "translator" in data or "cache" in data


class TestLanguagesEndpoint:
    """Tests for languages configuration endpoint"""
    
    @pytest.mark.integration
    def test_get_languages(self, api_client):
        """GET /languages should return supported languages"""
        response = api_client.get("/languages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "whisper_languages" in data
        assert "nllb_languages" in data
        assert "en" in data["whisper_languages"]
        assert "eng_Latn" in data["nllb_languages"]


class TestDocumentation:
    """Tests for API documentation endpoints"""
    
    @pytest.mark.integration
    def test_openapi_json(self, api_client):
        """GET /v1/openapi.json should return OpenAPI schema"""
        response = api_client.get("/v1/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data
    
    @pytest.mark.integration
    def test_docs_page(self, api_client):
        """GET /docs should return Swagger UI"""
        response = api_client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    @pytest.mark.integration
    def test_redoc_page(self, api_client):
        """GET /redoc should return ReDoc UI"""
        response = api_client.get("/redoc")
        
        assert response.status_code == 200


class TestTranslationEndpoint:
    """Tests for translation endpoint"""
    
    @pytest.mark.integration
    def test_translate_requires_auth(self, api_client, sample_translation_request):
        """POST /translate/text should require authentication"""
        response = api_client.post(
            "/translate/text",
            json=sample_translation_request
        )
        
        # Should fail without API key (401 or 403)
        assert response.status_code in [401, 403, 422]
    
    @pytest.mark.integration
    def test_translate_rejects_invalid_key(self, api_client, sample_translation_request, invalid_api_key_header):
        """POST /translate/text should reject invalid API key"""
        response = api_client.post(
            "/translate/text",
            json=sample_translation_request,
            headers=invalid_api_key_header
        )
        
        assert response.status_code in [401, 403]
    
    @pytest.mark.integration
    def test_translate_validates_input(self, api_client, invalid_api_key_header):
        """POST /translate/text should validate input"""
        response = api_client.post(
            "/translate/text",
            json={"text": "", "source_language": "en", "target_language": "fr"},
            headers=invalid_api_key_header
        )
        
        # Should fail validation or auth
        assert response.status_code in [400, 401, 403, 422]


class TestTranscriptionEndpoint:
    """Tests for transcription endpoint"""
    
    @pytest.mark.integration
    def test_transcribe_requires_auth(self, api_client):
        """POST /transcribe/audio should require authentication"""
        response = api_client.post("/transcribe/audio")
        
        assert response.status_code in [401, 403, 422]


class TestDevEndpoint:
    """Tests for development endpoints"""
    
    @pytest.mark.integration
    def test_dev_create_api_key_in_dev_mode(self, api_client):
        """POST /dev/create-api-key should work in development"""
        response = api_client.post("/dev/create-api-key?tier=pro")
        
        # In testing environment, should work
        if response.status_code == 200:
            data = response.json()
            assert "api_key" in data
            assert data["api_key"].startswith("tr_")
            assert "warning" in data
        else:
            # May be disabled
            assert response.status_code in [403, 503]


class TestRequestTracing:
    """Tests for request ID tracing"""
    
    @pytest.mark.integration
    def test_request_id_in_response(self, api_client):
        """Responses should include X-Request-ID header"""
        response = api_client.get("/")
        
        assert "X-Request-ID" in response.headers
    
    @pytest.mark.integration
    def test_custom_request_id_preserved(self, api_client):
        """Custom X-Request-ID should be preserved"""
        custom_id = "test-request-12345"
        response = api_client.get("/", headers={"X-Request-ID": custom_id})
        
        assert response.headers.get("X-Request-ID") == custom_id


class TestErrorHandling:
    """Tests for error handling"""
    
    @pytest.mark.integration
    def test_404_for_unknown_endpoint(self, api_client):
        """Unknown endpoints should return 404"""
        response = api_client.get("/nonexistent/endpoint")
        
        assert response.status_code == 404
    
    @pytest.mark.integration
    def test_405_for_wrong_method(self, api_client):
        """Wrong HTTP method should return 405"""
        response = api_client.delete("/")  # DELETE not allowed on root
        
        assert response.status_code == 405

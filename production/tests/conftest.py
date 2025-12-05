#!/usr/bin/env python3
"""
Shared Test Fixtures and Configuration
======================================

This module provides shared fixtures for all tests.
Fixtures are organized by scope: session > module > function
"""

import pytest
import sys
import os
from typing import Generator
from unittest.mock import MagicMock, AsyncMock

# Add production folder to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment BEFORE importing app modules
os.environ["ENVIRONMENT"] = "testing"
os.environ["WHISPER_MODEL"] = "tiny"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"


# =============================================================================
# SESSION-SCOPED FIXTURES (created once per test session)
# =============================================================================

@pytest.fixture(scope="session")
def test_config():
    """Test configuration values"""
    return {
        "api_base_url": "http://localhost:8000",
        "test_api_key": "tr_test_key_12345",
        "test_user_id": "test_user_001",
        "test_tier": "pro",
        "redis_host": "localhost",
        "redis_port": 6379,
    }


# =============================================================================
# MODULE-SCOPED FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def api_client():
    """
    FastAPI test client - shared across tests in a module
    """
    from fastapi.testclient import TestClient
    from api import app
    
    with TestClient(app) as client:
        yield client


# =============================================================================
# FUNCTION-SCOPED FIXTURES (created fresh for each test)
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for tests without Redis dependency"""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.incr.return_value = 1
    mock.decr.return_value = 0
    mock.hgetall.return_value = {
        "user_id": "test_user",
        "tier": "pro",
        "created_at": "2025-01-01T00:00:00",
        "requests_today": "0",
        "total_requests": "0"
    }
    mock.zremrangebyscore.return_value = 0
    mock.zcard.return_value = 5
    mock.zadd.return_value = 1
    mock.expire.return_value = True
    mock.pipeline.return_value.__enter__ = MagicMock(return_value=mock)
    mock.pipeline.return_value.__exit__ = MagicMock(return_value=False)
    mock.pipeline.return_value.execute.return_value = [0, 5, 1, True]
    return mock


@pytest.fixture
def mock_translator():
    """Mock AsyncRealtimeTranslator for tests without ML models"""
    mock = AsyncMock()
    mock.load_models = AsyncMock()
    mock.transcribe_audio = AsyncMock(return_value="Transcribed text")
    mock.translate_text = AsyncMock(return_value="Translated text")
    mock.process_audio = AsyncMock(return_value=("Original", "Translated"))
    mock.get_stats.return_value = {
        "total_requests": 100,
        "active_requests": 2,
        "max_concurrent_requests": 10,
        "failed_requests": 5,
        "success_rate": 95.0,
        "device": "cpu",
        "models_loaded": True
    }
    mock.cleanup = AsyncMock()
    return mock


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing"""
    import numpy as np
    # 1 second of silence at 16kHz
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def sample_translation_request():
    """Sample translation request payload"""
    return {
        "text": "Hello, world!",
        "source_language": "eng_Latn",
        "target_language": "fra_Latn"
    }


@pytest.fixture
def valid_api_key_header(test_config):
    """Headers with valid API key"""
    return {"X-API-Key": test_config["test_api_key"]}


@pytest.fixture
def invalid_api_key_header():
    """Headers with invalid API key"""
    return {"X-API-Key": "invalid_key"}


# =============================================================================
# ASYNC FIXTURES
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# MARKERS CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower)")
    config.addinivalue_line("markers", "slow: Slow tests (model loading, etc.)")
    config.addinivalue_line("markers", "requires_redis: Tests that require Redis")
    config.addinivalue_line("markers", "requires_gpu: Tests that require GPU")

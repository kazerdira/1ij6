#!/usr/bin/env python3
"""
Pytest Configuration and Fixtures
"""

import pytest
import sys
import os

# Add production folder to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def api_client():
    """Create test client for API"""
    # Import here to avoid loading models during test collection
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["WHISPER_MODEL"] = "tiny"  # Use smallest model for tests
    
    from api import app
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for tests without Redis"""
    mock = mocker.patch('redis.Redis')
    mock.return_value.ping.return_value = True
    mock.return_value.hgetall.return_value = {
        "user_id": "test_user",
        "tier": "pro",
        "created_at": "2025-01-01T00:00:00",
        "requests_today": "0",
        "total_requests": "0"
    }
    return mock


@pytest.fixture
def test_api_key():
    """Test API key for authenticated requests"""
    return "tr_test_key_for_unit_tests_only"

"""
Production API Test Suite
=========================

Organized test structure:
    tests/
    ├── __init__.py
    ├── conftest.py              # Shared fixtures
    ├── unit/                    # Unit tests (fast, isolated)
    │   ├── __init__.py
    │   ├── test_validators.py
    │   ├── test_circuit_breaker.py
    │   ├── test_rate_limiter.py
    │   └── test_cache.py
    ├── integration/             # Integration tests (slower, real services)
    │   ├── __init__.py
    │   ├── test_api_endpoints.py
    │   └── test_auth_flow.py
    └── fixtures/                # Test data and mocks
        ├── __init__.py
        ├── audio_samples.py
        └── mock_responses.py

Run tests:
    pytest                       # Run all tests
    pytest tests/unit            # Run only unit tests
    pytest tests/integration     # Run only integration tests
    pytest -v --tb=short         # Verbose with short traceback
    pytest --cov=.               # With coverage report
"""

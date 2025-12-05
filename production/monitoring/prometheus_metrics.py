#!/usr/bin/env python3
"""
Prometheus Metrics Exporter
Provides /metrics endpoint in Prometheus format
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, REGISTRY
    from prometheus_client.exposition import make_asgi_app
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus-client not installed. Install with: pip install prometheus-client")


if PROMETHEUS_AVAILABLE:
    # =============================================================================
    # METRICS DEFINITIONS
    # =============================================================================

    # Request metrics
    http_requests_total = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds',
        'HTTP request latency',
        ['method', 'endpoint'],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    # Translation metrics
    translations_total = Counter(
        'translations_total',
        'Total translations processed',
        ['source_lang', 'target_lang', 'cached']
    )

    translation_duration_seconds = Histogram(
        'translation_duration_seconds',
        'Translation processing time',
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
    )

    # Transcription metrics
    transcriptions_total = Counter(
        'transcriptions_total',
        'Total transcriptions processed',
        ['language', 'cached']
    )

    transcription_duration_seconds = Histogram(
        'transcription_duration_seconds',
        'Transcription processing time',
        buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
    )

    # Cache metrics
    cache_operations_total = Counter(
        'cache_operations_total',
        'Total cache operations',
        ['operation', 'result']  # operation: get/set/delete, result: hit/miss/error
    )

    # Circuit breaker metrics
    circuit_breaker_state = Gauge(
        'circuit_breaker_state',
        'Circuit breaker state (0=closed, 1=open, 2=half-open)',
        ['name']
    )

    circuit_breaker_failures_total = Counter(
        'circuit_breaker_failures_total',
        'Total circuit breaker failures',
        ['name']
    )

    # Model metrics
    model_loaded = Gauge(
        'model_loaded',
        'Model load status (1=loaded, 0=not loaded)',
        ['model_name']
    )

    model_inference_duration_seconds = Histogram(
        'model_inference_duration_seconds',
        'Model inference time',
        ['model_name'],
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
    )

    # System metrics
    active_requests = Gauge(
        'active_requests',
        'Number of active requests'
    )

    # Rate limiting metrics
    rate_limit_exceeded_total = Counter(
        'rate_limit_exceeded_total',
        'Total rate limit violations',
        ['tier']
    )

    # API key metrics
    api_key_usage_total = Counter(
        'api_key_usage_total',
        'API key usage',
        ['user_id', 'tier']
    )

    # Error metrics
    errors_total = Counter(
        'errors_total',
        'Total errors',
        ['error_type', 'endpoint']
    )

    # Application info
    app_info = Info('app', 'Application information')
    app_info.info({
        'version': '1.0.0',
        'environment': 'production'
    })

    # Create Prometheus ASGI app for /metrics endpoint
    metrics_app = make_asgi_app()

else:
    # Stub if prometheus not available
    metrics_app = None


# =============================================================================
# METRICS HELPER CLASS
# =============================================================================

class MetricsHelper:
    """Helper class for recording metrics"""
    
    @staticmethod
    def record_request(method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        if not PROMETHEUS_AVAILABLE:
            return
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    @staticmethod
    def record_translation(source_lang: str, target_lang: str, cached: bool, duration: float):
        """Record translation metrics"""
        if not PROMETHEUS_AVAILABLE:
            return
        translations_total.labels(
            source_lang=source_lang,
            target_lang=target_lang,
            cached='true' if cached else 'false'
        ).inc()
        translation_duration_seconds.observe(duration)
    
    @staticmethod
    def record_transcription(language: str, cached: bool, duration: float):
        """Record transcription metrics"""
        if not PROMETHEUS_AVAILABLE:
            return
        transcriptions_total.labels(
            language=language,
            cached='true' if cached else 'false'
        ).inc()
        transcription_duration_seconds.observe(duration)
    
    @staticmethod
    def record_cache_operation(operation: str, result: str):
        """Record cache operation"""
        if not PROMETHEUS_AVAILABLE:
            return
        cache_operations_total.labels(operation=operation, result=result).inc()
    
    @staticmethod
    def update_circuit_breaker_state(name: str, state: str):
        """Update circuit breaker state"""
        if not PROMETHEUS_AVAILABLE:
            return
        state_map = {'closed': 0, 'open': 1, 'half_open': 2}
        circuit_breaker_state.labels(name=name).set(state_map.get(state, 0))
    
    @staticmethod
    def record_circuit_breaker_failure(name: str):
        """Record circuit breaker failure"""
        if not PROMETHEUS_AVAILABLE:
            return
        circuit_breaker_failures_total.labels(name=name).inc()
    
    @staticmethod
    def update_model_status(model_name: str, loaded: bool):
        """Update model load status"""
        if not PROMETHEUS_AVAILABLE:
            return
        model_loaded.labels(model_name=model_name).set(1 if loaded else 0)
    
    @staticmethod
    def record_model_inference(model_name: str, duration: float):
        """Record model inference time"""
        if not PROMETHEUS_AVAILABLE:
            return
        model_inference_duration_seconds.labels(model_name=model_name).observe(duration)
    
    @staticmethod
    def set_active_requests(count: int):
        """Set active requests gauge"""
        if not PROMETHEUS_AVAILABLE:
            return
        active_requests.set(count)
    
    @staticmethod
    def record_rate_limit_exceeded(tier: str):
        """Record rate limit violation"""
        if not PROMETHEUS_AVAILABLE:
            return
        rate_limit_exceeded_total.labels(tier=tier).inc()
    
    @staticmethod
    def record_api_key_usage(user_id: str, tier: str):
        """Record API key usage"""
        if not PROMETHEUS_AVAILABLE:
            return
        api_key_usage_total.labels(user_id=user_id, tier=tier).inc()
    
    @staticmethod
    def record_error(error_type: str, endpoint: str):
        """Record error"""
        if not PROMETHEUS_AVAILABLE:
            return
        errors_total.labels(error_type=error_type, endpoint=endpoint).inc()


# Export
__all__ = ['MetricsHelper', 'metrics_app', 'PROMETHEUS_AVAILABLE']

#!/usr/bin/env python3
"""
Circuit Breaker Pattern
Prevents cascading failures and allows system recovery
"""

from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
import functools
import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation
    
    Tracks failures and opens circuit to prevent cascading failures.
    After timeout, enters half-open state to test recovery.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default"
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        
        # Track recent failures for analysis
        self.recent_failures = deque(maxlen=100)
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
    
    def __enter__(self):
        """Context manager entry"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit '{self.name}' entering HALF_OPEN state")
            else:
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Will retry at {self.last_failure_time + timedelta(seconds=self.recovery_timeout)}"
                )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.total_calls += 1
        
        if exc_type and issubclass(exc_type, self.expected_exception):
            # Failure occurred
            self._on_failure()
            return False  # Re-raise exception
        else:
            # Success
            self._on_success()
            return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
    
    def _on_failure(self):
        """Handle failure"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now()
        
        # Track failure
        self.recent_failures.append({
            'timestamp': self.last_failure_time,
            'failure_count': self.failure_count
        })
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit '{self.name}' re-opened after failed recovery test")
        
        elif self.failure_count >= self.failure_threshold:
            # Too many failures, open circuit
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit '{self.name}' OPENED after {self.failure_count} failures. "
                f"Will attempt recovery in {self.recovery_timeout}s"
            )
    
    def _on_success(self):
        """Handle success"""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Recovery test succeeded
            self.failure_count = 0
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit '{self.name}' CLOSED after successful recovery")
        
        # Gradually reduce failure count on success
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        logger.info(f"Circuit '{self.name}' manually reset")
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        success_rate = 0
        if self.total_calls > 0:
            success_rate = (self.total_successes / self.total_calls) * 100
        
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'total_calls': self.total_calls,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'success_rate': round(success_rate, 2),
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None
        }


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: str = None
):
    """
    Decorator for circuit breaker pattern
    
    Usage:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        def my_function():
            # Function that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        breaker_name = name or func.__name__
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with breaker:
                return func(*args, **kwargs)
        
        # Attach breaker to function for inspection
        wrapper.circuit_breaker = breaker
        
        return wrapper
    return decorator


def async_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: str = None
):
    """
    Async version of circuit breaker decorator
    
    Usage:
        @async_circuit_breaker(failure_threshold=3)
        async def my_async_function():
            # Async function that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        breaker_name = name or func.__name__
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with breaker:
                return await func(*args, **kwargs)
        
        wrapper.circuit_breaker = breaker
        
        return wrapper
    return decorator


class CircuitBreakerRegistry:
    """Registry to manage multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}
    
    def register(self, breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self.breakers[breaker.name] = breaker
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self.breakers.get(name)
    
    def get_all_stats(self) -> list[dict]:
        """Get stats for all circuit breakers"""
        return [breaker.get_stats() for breaker in self.breakers.values()]
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()


# Global registry
registry = CircuitBreakerRegistry()


# Example usage:
"""
# Synchronous function
@circuit_breaker(failure_threshold=3, recovery_timeout=30, name="model_inference")
def call_model(input_data):
    # Call model that might fail
    return model.predict(input_data)

# Async function
@async_circuit_breaker(failure_threshold=5, recovery_timeout=60, name="translation_api")
async def translate_text(text):
    # Async translation call
    return await translation_service.translate(text)

# Check circuit breaker stats
from reliability.circuit_breaker import registry

stats = registry.get_all_stats()
print(stats)
"""

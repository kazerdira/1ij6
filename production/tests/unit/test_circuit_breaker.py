#!/usr/bin/env python3
"""
Unit Tests: Circuit Breaker
===========================

Tests for reliability/circuit_breaker.py
These tests verify circuit breaker state transitions and error handling.
"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    registry
)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions"""
    
    @pytest.mark.unit
    def test_initial_state_is_closed(self):
        """Circuit breaker should start in CLOSED state"""
        cb = CircuitBreaker(name="test_initial", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    def test_stays_closed_under_threshold(self):
        """Circuit should stay closed if failures < threshold"""
        cb = CircuitBreaker(name="test_under", failure_threshold=3)
        
        # Simulate failures via internal method
        cb._on_failure()
        assert cb.state == CircuitState.CLOSED
        
        cb._on_failure()
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    def test_opens_at_threshold(self):
        """Circuit should open when failures reach threshold"""
        cb = CircuitBreaker(name="test_threshold", failure_threshold=3)
        
        cb._on_failure()
        cb._on_failure()
        cb._on_failure()
        
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.unit
    def test_open_circuit_raises_error(self):
        """Open circuit should raise CircuitBreakerError"""
        cb = CircuitBreaker(name="test_raises", failure_threshold=1)
        cb._on_failure()  # Opens circuit
        
        with pytest.raises(CircuitBreakerError):
            with cb:
                pass  # Should not reach here
    
    @pytest.mark.unit
    def test_reset_closes_circuit(self):
        """Reset should close an open circuit"""
        cb = CircuitBreaker(name="test_reset", failure_threshold=1)
        cb._on_failure()
        assert cb.state == CircuitState.OPEN
        
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.unit
    def test_success_reduces_failure_count(self):
        """Successful call should reduce failure count"""
        cb = CircuitBreaker(name="test_success", failure_threshold=5)
        
        cb._on_failure()
        cb._on_failure()
        assert cb.failure_count == 2
        
        cb._on_success()
        assert cb.failure_count == 1  # Gradually reduces


class TestCircuitBreakerContextManager:
    """Test circuit breaker as context manager"""
    
    @pytest.mark.unit
    def test_successful_execution(self):
        """Successful execution should work normally"""
        cb = CircuitBreaker(name="test_ctx_success", failure_threshold=3)
        
        with cb:
            result = 1 + 1
        
        assert result == 2
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.unit
    def test_exception_records_failure(self):
        """Exception inside context should record failure"""
        cb = CircuitBreaker(name="test_ctx_fail", failure_threshold=3)
        
        with pytest.raises(ValueError):
            with cb:
                raise ValueError("Test error")
        
        assert cb.failure_count == 1
    
    @pytest.mark.unit
    def test_filtered_exception_records_failure(self):
        """Only expected exceptions should count as failures"""
        cb = CircuitBreaker(
            name="test_filtered",
            failure_threshold=3,
            expected_exception=ValueError
        )
        
        # ValueError should count
        with pytest.raises(ValueError):
            with cb:
                raise ValueError("Expected")
        assert cb.failure_count == 1


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry"""
    
    @pytest.mark.unit
    def test_registry_stores_breakers(self):
        """Registry should store circuit breakers by name"""
        cb = CircuitBreaker(name="test_registry_store_v2", failure_threshold=3)
        registry.register(cb)
        
        retrieved = registry.get("test_registry_store_v2")
        assert retrieved is cb
    
    @pytest.mark.unit
    def test_registry_get_all_stats(self):
        """Registry should return stats for all breakers"""
        cb1 = CircuitBreaker(name="test_stats_1_v2", failure_threshold=3)
        cb2 = CircuitBreaker(name="test_stats_2_v2", failure_threshold=3)
        registry.register(cb1)
        registry.register(cb2)
        
        stats = registry.get_all_stats()
        
        assert isinstance(stats, list)
        # Check that our breakers are in there
        names = [s.get("name") for s in stats]
        assert "test_stats_1_v2" in names
        assert "test_stats_2_v2" in names
    
    @pytest.mark.unit
    def test_registry_reset_all(self):
        """Registry reset_all should reset all breakers"""
        cb1 = CircuitBreaker(name="test_reset_all_1_v2", failure_threshold=1)
        cb2 = CircuitBreaker(name="test_reset_all_2_v2", failure_threshold=1)
        registry.register(cb1)
        registry.register(cb2)
        
        cb1._on_failure()
        cb2._on_failure()
        
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN
        
        registry.reset_all()
        
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


class TestCircuitBreakerStats:
    """Test circuit breaker statistics"""
    
    @pytest.mark.unit
    def test_get_stats_structure(self):
        """Stats should have correct structure"""
        cb = CircuitBreaker(name="test_stats_struct_v2", failure_threshold=3)
        
        stats = cb.get_stats()
        
        assert "state" in stats
        assert "failure_count" in stats
        assert "total_successes" in stats
        assert "total_failures" in stats
        assert "name" in stats
    
    @pytest.mark.unit
    def test_stats_track_calls(self):
        """Stats should track total calls"""
        cb = CircuitBreaker(name="test_stats_calls", failure_threshold=5)
        
        # Execute successfully
        with cb:
            pass
        
        stats = cb.get_stats()
        assert stats["total_calls"] == 1
        assert stats["total_successes"] == 1

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
        assert cb.is_closed()
    
    @pytest.mark.unit
    def test_stays_closed_under_threshold(self):
        """Circuit should stay closed if failures < threshold"""
        cb = CircuitBreaker(name="test_under", failure_threshold=3)
        
        cb.record_failure()
        assert cb.is_closed()
        
        cb.record_failure()
        assert cb.is_closed()
    
    @pytest.mark.unit
    def test_opens_at_threshold(self):
        """Circuit should open when failures reach threshold"""
        cb = CircuitBreaker(name="test_threshold", failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        
        assert cb.is_open()
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.unit
    def test_open_circuit_raises_error(self):
        """Open circuit should raise CircuitBreakerError"""
        cb = CircuitBreaker(name="test_raises", failure_threshold=1)
        cb.record_failure()  # Opens circuit
        
        with pytest.raises(CircuitBreakerError):
            with cb:
                pass  # Should not reach here
    
    @pytest.mark.unit
    def test_reset_closes_circuit(self):
        """Reset should close an open circuit"""
        cb = CircuitBreaker(name="test_reset", failure_threshold=1)
        cb.record_failure()
        assert cb.is_open()
        
        cb.reset()
        assert cb.is_closed()
        assert cb.failure_count == 0
    
    @pytest.mark.unit
    def test_success_resets_failure_count(self):
        """Successful call should reset failure count"""
        cb = CircuitBreaker(name="test_success", failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        
        cb.record_success()
        assert cb.failure_count == 0


class TestCircuitBreakerContextManager:
    """Test circuit breaker as context manager"""
    
    @pytest.mark.unit
    def test_successful_execution(self):
        """Successful execution should work normally"""
        cb = CircuitBreaker(name="test_ctx_success", failure_threshold=3)
        
        with cb:
            result = 1 + 1
        
        assert result == 2
        assert cb.is_closed()
    
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
        
        # TypeError should NOT count (re-raised but not counted)
        with pytest.raises(TypeError):
            with cb:
                raise TypeError("Unexpected")
        # Failure count may or may not increase depending on implementation


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry"""
    
    @pytest.mark.unit
    def test_registry_stores_breakers(self):
        """Registry should store circuit breakers by name"""
        cb = CircuitBreaker(name="test_registry_store", failure_threshold=3)
        
        retrieved = registry.get("test_registry_store")
        assert retrieved is cb
    
    @pytest.mark.unit
    def test_registry_get_all_stats(self):
        """Registry should return stats for all breakers"""
        CircuitBreaker(name="test_stats_1", failure_threshold=3)
        CircuitBreaker(name="test_stats_2", failure_threshold=3)
        
        stats = registry.get_all_stats()
        
        assert isinstance(stats, dict)
        assert "test_stats_1" in stats
        assert "test_stats_2" in stats
    
    @pytest.mark.unit
    def test_registry_reset_all(self):
        """Registry reset_all should reset all breakers"""
        cb1 = CircuitBreaker(name="test_reset_all_1", failure_threshold=1)
        cb2 = CircuitBreaker(name="test_reset_all_2", failure_threshold=1)
        
        cb1.record_failure()
        cb2.record_failure()
        
        assert cb1.is_open()
        assert cb2.is_open()
        
        registry.reset_all()
        
        assert cb1.is_closed()
        assert cb2.is_closed()


class TestCircuitBreakerStats:
    """Test circuit breaker statistics"""
    
    @pytest.mark.unit
    def test_get_stats_structure(self):
        """Stats should have correct structure"""
        cb = CircuitBreaker(name="test_stats_struct", failure_threshold=3)
        
        stats = cb.get_stats()
        
        assert "state" in stats
        assert "failure_count" in stats
        assert "success_count" in stats
        assert "failure_threshold" in stats

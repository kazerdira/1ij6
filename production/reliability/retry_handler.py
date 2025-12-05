#!/usr/bin/env python3
"""
Retry Handler with Exponential Backoff
Automatically retry failed operations with increasing delays
"""

import time
import random
import functools
import asyncio
import logging
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted"""
    pass


class RetryHandler:
    """
    Retry handler with exponential backoff and jitter
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        Initialize retry handler
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff (2 = double each time)
            jitter: Add randomization to prevent thundering herd
            exceptions: Tuple of exceptions to catch and retry
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add jitter: random value between 0 and delay
            delay = random.uniform(0, delay)
        
        return delay
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to add retry logic"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except self.exceptions as e:
                    last_exception = e
                    
                    if attempt < self.max_attempts - 1:
                        delay = self.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{self.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {self.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
            
            # All retries exhausted
            raise RetryExhausted(
                f"Failed after {self.max_attempts} attempts. Last error: {last_exception}"
            ) from last_exception
        
        return wrapper


class AsyncRetryHandler:
    """Async version of retry handler"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            delay = random.uniform(0, delay)
        
        return delay
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to add async retry logic"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except self.exceptions as e:
                    last_exception = e
                    
                    if attempt < self.max_attempts - 1:
                        delay = self.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{self.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {self.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
            
            raise RetryExhausted(
                f"Failed after {self.max_attempts} attempts. Last error: {last_exception}"
            ) from last_exception
        
        return wrapper


# Convenience decorators
def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Simple retry decorator
    
    Usage:
        @retry(max_attempts=3, base_delay=1.0)
        def my_function():
            # Function that might fail
            pass
    """
    return RetryHandler(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=exceptions
    )


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Simple async retry decorator
    
    Usage:
        @async_retry(max_attempts=3)
        async def my_async_function():
            # Async function that might fail
            pass
    """
    return AsyncRetryHandler(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=exceptions
    )


# Specific retry strategies
def retry_on_connection_error(max_attempts: int = 5):
    """Retry on connection errors"""
    return RetryHandler(
        max_attempts=max_attempts,
        base_delay=1.0,
        max_delay=30.0,
        exceptions=(ConnectionError, TimeoutError, OSError)
    )


def retry_on_model_error(max_attempts: int = 3):
    """Retry on model/GPU errors"""
    try:
        import torch
        return RetryHandler(
            max_attempts=max_attempts,
            base_delay=2.0,
            max_delay=60.0,
            exceptions=(RuntimeError, torch.cuda.OutOfMemoryError)
        )
    except ImportError:
        return RetryHandler(
            max_attempts=max_attempts,
            base_delay=2.0,
            max_delay=60.0,
            exceptions=(RuntimeError,)
        )


class AdvancedRetryHandler:
    """
    Advanced retry handler with additional features
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        on_retry: Optional[Callable] = None,
        on_failure: Optional[Callable] = None
    ):
        """
        Advanced retry handler with callbacks
        
        Args:
            on_retry: Callback called before each retry (attempt, exception)
            on_failure: Callback called when all retries exhausted (exception)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions
        self.on_retry = on_retry
        self.on_failure = on_failure
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            delay = random.uniform(0, delay)
        
        return delay
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - reset any failure tracking
                    if hasattr(func, '_retry_failure_count'):
                        func._retry_failure_count = 0
                    
                    return result
                
                except self.exceptions as e:
                    last_exception = e
                    
                    # Track failures
                    if not hasattr(func, '_retry_failure_count'):
                        func._retry_failure_count = 0
                    func._retry_failure_count += 1
                    
                    if attempt < self.max_attempts - 1:
                        delay = self.calculate_delay(attempt)
                        
                        # Call retry callback
                        if self.on_retry:
                            self.on_retry(attempt + 1, e)
                        
                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_attempts} for {func.__name__}: {e}. "
                            f"Waiting {delay:.2f}s..."
                        )
                        
                        time.sleep(delay)
                    else:
                        # Call failure callback
                        if self.on_failure:
                            self.on_failure(e)
                        
                        logger.error(
                            f"All {self.max_attempts} attempts exhausted for {func.__name__}"
                        )
            
            raise RetryExhausted(
                f"Failed after {self.max_attempts} attempts. Last error: {last_exception}"
            ) from last_exception
        
        return wrapper

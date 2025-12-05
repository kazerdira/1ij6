#!/usr/bin/env python3
"""
Cache Manager with Redis
Cache translations to avoid redundant processing
"""

import redis
import hashlib
import json
import pickle
from typing import Optional, Any
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based cache manager for translations"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600  # 1 hour
    ):
        """
        Initialize cache manager
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            default_ttl: Default time-to-live in seconds
        """
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False,  # Handle binary data
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"Cache manager connected to Redis at {host}:{port}")
        
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None
            self.enabled = False
        
        self.default_ttl = default_ttl
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.sets = 0
    
    def _generate_key(self, prefix: str, data: Any) -> str:
        """
        Generate cache key from data
        
        Args:
            prefix: Key prefix
            data: Data to hash
        
        Returns:
            Cache key
        """
        # Create hash of data
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, sort_keys=True)
        
        hash_hex = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_hex}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        if not self.enabled:
            self.misses += 1
            return None
        
        try:
            value = self.redis_client.get(key)
            
            if value is None:
                self.misses += 1
                return None
            
            # Deserialize
            deserialized = pickle.loads(value)
            self.hits += 1
            
            logger.debug(f"Cache HIT: {key}")
            return deserialized
        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = default)
        """
        if not self.enabled:
            return
        
        try:
            # Serialize
            serialized = pickle.dumps(value)
            
            # Set with TTL
            ttl = ttl or self.default_ttl
            self.redis_client.setex(key, ttl, serialized)
            
            self.sets += 1
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        if not self.enabled:
            return
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
    
    def clear_pattern(self, pattern: str):
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Redis key pattern (e.g., "translation:*")
        """
        if not self.enabled:
            return
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} keys matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
    
    def clear_all(self):
        """Clear entire cache"""
        if not self.enabled:
            return
        
        try:
            self.redis_client.flushdb()
            logger.info("Cache cleared (flushdb)")
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'enabled': self.enabled,
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'hit_rate': round(hit_rate, 2)
        }
        
        if self.enabled:
            try:
                info = self.redis_client.info()
                stats['redis_memory_used_mb'] = round(
                    info.get('used_memory', 0) / (1024 * 1024), 2
                )
                stats['redis_connected_clients'] = info.get('connected_clients', 0)
            except Exception as e:
                logger.error(f"Error getting Redis info: {e}")
        
        return stats


class TranslationCache:
    """Specialized cache for translations"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.prefix = "translation"
    
    def get_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[str]:
        """
        Get cached translation
        
        Args:
            text: Source text
            source_lang: Source language
            target_lang: Target language
        
        Returns:
            Translated text or None
        """
        cache_data = {
            'text': text,
            'source': source_lang,
            'target': target_lang
        }
        key = self.cache._generate_key(self.prefix, cache_data)
        return self.cache.get(key)
    
    def set_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation: str,
        ttl: int = 86400  # 24 hours default
    ):
        """
        Cache translation
        
        Args:
            text: Source text
            source_lang: Source language
            target_lang: Target language
            translation: Translated text
            ttl: Time-to-live in seconds
        """
        cache_data = {
            'text': text,
            'source': source_lang,
            'target': target_lang
        }
        key = self.cache._generate_key(self.prefix, cache_data)
        self.cache.set(key, translation, ttl)


class TranscriptionCache:
    """Specialized cache for audio transcriptions"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.prefix = "transcription"
    
    def get_transcription(
        self,
        audio_hash: str,
        language: str
    ) -> Optional[str]:
        """
        Get cached transcription
        
        Args:
            audio_hash: Hash of audio data
            language: Source language
        
        Returns:
            Transcribed text or None
        """
        cache_data = {
            'audio_hash': audio_hash,
            'language': language
        }
        key = self.cache._generate_key(self.prefix, cache_data)
        return self.cache.get(key)
    
    def set_transcription(
        self,
        audio_hash: str,
        language: str,
        transcription: str,
        ttl: int = 86400
    ):
        """
        Cache transcription
        
        Args:
            audio_hash: Hash of audio data
            language: Source language
            transcription: Transcribed text
            ttl: Time-to-live in seconds
        """
        cache_data = {
            'audio_hash': audio_hash,
            'language': language
        }
        key = self.cache._generate_key(self.prefix, cache_data)
        self.cache.set(key, transcription, ttl)


def hash_audio(audio_data: bytes) -> str:
    """
    Generate hash for audio data
    
    Args:
        audio_data: Audio bytes
    
    Returns:
        Hash string
    """
    return hashlib.sha256(audio_data).hexdigest()


# Global cache instance
cache_manager = CacheManager()
translation_cache = TranslationCache(cache_manager)
transcription_cache = TranscriptionCache(cache_manager)


# Example usage:
"""
from scalability.cache_manager import translation_cache, transcription_cache, hash_audio

# Check translation cache
cached_translation = translation_cache.get_translation(
    text="안녕하세요",
    source_lang="ko",
    target_lang="eng_Latn"
)

if cached_translation:
    print(f"Cache hit: {cached_translation}")
else:
    # Perform translation
    translation = translator.translate("안녕하세요")
    
    # Cache result
    translation_cache.set_translation(
        text="안녕하세요",
        source_lang="ko",
        target_lang="eng_Latn",
        translation=translation
    )

# Check transcription cache
audio_hash = hash_audio(audio_bytes)
cached_transcription = transcription_cache.get_transcription(
    audio_hash=audio_hash,
    language="ko"
)
"""

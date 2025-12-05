#!/usr/bin/env python3
"""
Unit Tests: Cache Manager
=========================

Tests for scalability/cache_manager.py
These tests verify caching logic and Redis interactions.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestCacheManagerBasics:
    """Basic cache manager functionality tests"""
    
    @pytest.mark.unit
    def test_cache_manager_import(self):
        """CacheManager should be importable"""
        from scalability.cache_manager import CacheManager
        assert CacheManager is not None
    
    @pytest.mark.unit
    def test_cache_manager_disabled_without_redis(self):
        """Cache manager should work gracefully without Redis"""
        from scalability.cache_manager import CacheManager
        
        # Force no Redis connection
        with patch('scalability.cache_manager.REDIS_AVAILABLE', False):
            manager = CacheManager()
            assert manager.enabled is False
    
    @pytest.mark.unit
    def test_cache_manager_statistics_initialized(self):
        """Cache manager should initialize statistics"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        
        assert hasattr(manager, 'hits')
        assert hasattr(manager, 'misses')
        assert hasattr(manager, 'sets')
        assert manager.hits == 0
        assert manager.misses == 0
        assert manager.sets == 0


class TestCacheOperations:
    """Tests for cache get/set operations"""
    
    @pytest.mark.unit
    def test_get_returns_none_when_disabled(self):
        """get() should return None when cache is disabled"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.enabled = False
        
        result = manager.get("any_key")
        
        assert result is None
        assert manager.misses == 1
    
    @pytest.mark.unit
    def test_get_with_mock_redis(self, mock_redis):
        """get() should deserialize cached value"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.redis_client = mock_redis
        manager.enabled = True
        
        # Mock Redis returning pickled data
        test_value = {"text": "Hello", "translation": "Bonjour"}
        mock_redis.get.return_value = pickle.dumps(test_value)
        
        result = manager.get("test_key")
        
        assert result == test_value
        assert manager.hits == 1
    
    @pytest.mark.unit
    def test_get_cache_miss(self, mock_redis):
        """get() should increment misses on cache miss"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.redis_client = mock_redis
        manager.enabled = True
        
        mock_redis.get.return_value = None
        
        result = manager.get("nonexistent_key")
        
        assert result is None
        assert manager.misses == 1
    
    @pytest.mark.unit
    def test_set_does_nothing_when_disabled(self):
        """set() should do nothing when cache is disabled"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.enabled = False
        
        # Should not raise
        manager.set("key", "value")
        
        assert manager.sets == 0
    
    @pytest.mark.unit
    def test_set_with_mock_redis(self, mock_redis):
        """set() should serialize and store value"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.redis_client = mock_redis
        manager.enabled = True
        
        manager.set("test_key", {"data": "value"}, ttl=3600)
        
        mock_redis.setex.assert_called_once()
        assert manager.sets == 1


class TestCacheKeyGeneration:
    """Tests for cache key generation"""
    
    @pytest.mark.unit
    def test_generate_key_from_string(self):
        """Should generate consistent key from string"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        
        key1 = manager._generate_key("prefix", "test data")
        key2 = manager._generate_key("prefix", "test data")
        
        assert key1 == key2
        assert key1.startswith("prefix:")
    
    @pytest.mark.unit
    def test_generate_key_different_data(self):
        """Different data should produce different keys"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        
        key1 = manager._generate_key("prefix", "data1")
        key2 = manager._generate_key("prefix", "data2")
        
        assert key1 != key2
    
    @pytest.mark.unit
    def test_generate_key_from_dict(self):
        """Should generate key from dict (JSON serialized)"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        
        data = {"text": "hello", "lang": "en"}
        key = manager._generate_key("translation", data)
        
        assert key.startswith("translation:")


class TestCacheStatistics:
    """Tests for cache statistics"""
    
    @pytest.mark.unit
    def test_get_stats_structure(self):
        """get_stats() should return proper structure"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        stats = manager.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "hit_rate" in stats
        assert "enabled" in stats
    
    @pytest.mark.unit
    def test_hit_rate_calculation(self):
        """Hit rate should be calculated correctly"""
        from scalability.cache_manager import CacheManager
        
        manager = CacheManager()
        manager.hits = 80
        manager.misses = 20
        
        stats = manager.get_stats()
        
        assert stats["hit_rate"] == 80.0  # 80 / 100 * 100


class TestTranslationCache:
    """Tests for translation-specific caching"""
    
    @pytest.mark.unit
    def test_translation_cache_import(self):
        """TranslationCache should be importable"""
        from scalability.cache_manager import TranslationCache
        assert TranslationCache is not None
    
    @pytest.mark.unit
    def test_translation_cache_key_format(self):
        """Translation cache should create proper keys"""
        from scalability.cache_manager import TranslationCache, cache_manager
        
        tc = TranslationCache(cache_manager)
        
        # Just verify the cache can be instantiated
        assert tc is not None


class TestAudioHashing:
    """Tests for audio hashing utility"""
    
    @pytest.mark.unit
    def test_hash_audio_import(self):
        """hash_audio should be importable"""
        from scalability.cache_manager import hash_audio
        assert hash_audio is not None
    
    @pytest.mark.unit
    def test_hash_audio_consistency(self):
        """Same audio data should produce same hash"""
        from scalability.cache_manager import hash_audio
        
        audio_bytes = b"fake audio data for testing"
        
        hash1 = hash_audio(audio_bytes)
        hash2 = hash_audio(audio_bytes)
        
        assert hash1 == hash2
    
    @pytest.mark.unit
    def test_hash_audio_different_data(self):
        """Different audio should produce different hash"""
        from scalability.cache_manager import hash_audio
        
        hash1 = hash_audio(b"audio data 1")
        hash2 = hash_audio(b"audio data 2")
        
        assert hash1 != hash2

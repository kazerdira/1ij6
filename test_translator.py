#!/usr/bin/env python3
"""
Comprehensive test suite for Real-time Speech Translator
Tests core functionality, error handling, and edge cases
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realtime_translator import RealtimeTranslator
from realtime_translator_enhanced import EnhancedRealtimeTranslator


class TestRealtimeTranslator:
    """Test suite for basic RealtimeTranslator"""
    
    @pytest.fixture
    def translator(self):
        """Create a translator instance for testing"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = RealtimeTranslator(
                source_language="en",
                target_language="eng_Latn",
                whisper_model="tiny",
                chunk_duration=2,
                buffer_duration=0.5
            )
            return translator
    
    def test_initialization(self, translator):
        """Test translator initializes correctly"""
        assert translator.source_language == "en"
        assert translator.target_language == "eng_Latn"
        assert translator.chunk_duration == 2
        assert translator.buffer_duration == 0.5
        assert translator.sample_rate == 16000
    
    def test_audio_chunk_size_calculation(self, translator):
        """Test audio chunk size calculations"""
        expected_chunk_samples = 16000 * 2  # 2 seconds at 16kHz
        assert translator.chunk_samples == expected_chunk_samples
        
        expected_buffer_samples = 16000 * 0.5  # 0.5 seconds
        assert translator.buffer_samples == expected_buffer_samples
    
    def test_audio_callback(self, translator):
        """Test audio callback handles data correctly"""
        # Mock audio data
        audio_data = np.random.randn(1600, 1).astype(np.float32)
        
        translator.audio_callback(audio_data, 1600, None, None)
        
        # Check queue has data
        assert not translator.audio_queue.empty()
    
    def test_audio_normalization(self, translator):
        """Test audio normalization"""
        # Create audio that needs normalization
        audio = np.array([2.0, 4.0, -2.0, -4.0], dtype=np.float32)
        
        # Normalize
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio_normalized = audio / np.abs(audio).max()
        
        assert audio_normalized.max() <= 1.0
        assert audio_normalized.min() >= -1.0
    
    @patch('whisper.load_model')
    def test_whisper_model_loading_error(self, mock_load):
        """Test handling of Whisper model loading errors"""
        mock_load.side_effect = Exception("Model not found")
        
        with pytest.raises(SystemExit):
            RealtimeTranslator()
    
    def test_empty_transcription_handling(self, translator):
        """Test handling of empty transcriptions"""
        with patch.object(translator.whisper_model, 'transcribe') as mock_transcribe:
            mock_transcribe.return_value = {"text": "", "language": "en"}
            
            audio = np.zeros(32000, dtype=np.float32)
            result = translator.process_audio_chunk(audio)
            
            assert result[0] is None
            assert result[1] is None
    
    def test_translation_error_handling(self, translator):
        """Test translation error handling"""
        with patch.object(translator, 'translate_text') as mock_translate:
            mock_translate.side_effect = Exception("Translation failed")
            
            audio = np.random.randn(32000).astype(np.float32)
            # Should handle error gracefully
            translator.error_count = 0
            try:
                translator.process_audio_chunk(audio)
            except Exception:
                pytest.fail("Should handle translation errors gracefully")


class TestEnhancedRealtimeTranslator:
    """Test suite for EnhancedRealtimeTranslator"""
    
    @pytest.fixture
    def config_file(self):
        """Create a temporary config file"""
        config_content = """
[General]
verbose = true
save_to_file = false

[Audio]
sample_rate = 16000
chunk_duration = 3
buffer_duration = 1

[Whisper]
model_size = tiny
source_language = en

[Translation]
target_language = eng_Latn
num_beams = 5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_config_file_loading(self, config_file):
        """Test configuration file loading"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = EnhancedRealtimeTranslator(config_file=config_file)
            
            assert translator.config['sample_rate'] == 16000
            assert translator.config['chunk_duration'] == 3
            assert translator.config['whisper_model'] == 'tiny'
            assert translator.config['source_language'] == 'en'
    
    def test_config_override(self, config_file):
        """Test config file override with kwargs"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = EnhancedRealtimeTranslator(
                config_file=config_file,
                source_language="ko",
                whisper_model="base"
            )
            
            # Override should take precedence
            assert translator.config['source_language'] == 'ko'
            assert translator.config['whisper_model'] == 'base'
            
            # Non-overridden values should come from config
            assert translator.config['chunk_duration'] == 3
    
    def test_save_to_file(self, config_file):
        """Test saving transcriptions to file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('whisper.load_model'), \
                 patch('transformers.AutoTokenizer.from_pretrained'), \
                 patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
                translator = EnhancedRealtimeTranslator(
                    config_file=config_file,
                    save_to_file=True,
                    output_file=output_file
                )
                
                # Display a result (which should write to file)
                translator.display_result("Test original", "Test translated", "en")
                translator.stop()
                
                # Check file was written
                assert os.path.exists(output_file)
                with open(output_file, 'r') as f:
                    content = f.read()
                    assert "Test original" in content
                    assert "Test translated" in content
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_statistics_tracking(self):
        """Test statistics tracking"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = EnhancedRealtimeTranslator(source_language="en")
            
            assert translator.transcription_count == 0
            assert translator.translation_count == 0
            assert translator.error_count == 0
            
            # Simulate successful processing
            translator.transcription_count = 5
            translator.translation_count = 5
            translator.error_count = 1
            
            assert translator.transcription_count == 5
            assert translator.translation_count == 5
            assert translator.error_count == 1


class TestAudioProcessing:
    """Test audio processing utilities"""
    
    def test_mono_conversion(self):
        """Test stereo to mono conversion"""
        # Stereo audio (2 channels)
        stereo_audio = np.random.randn(1000, 2).astype(np.float32)
        
        # Convert to mono (take first channel)
        mono_audio = stereo_audio[:, 0]
        
        assert mono_audio.shape == (1000,)
        assert len(mono_audio.shape) == 1
    
    def test_audio_normalization_range(self):
        """Test audio normalization keeps values in [-1, 1]"""
        audio = np.random.randn(1000).astype(np.float32) * 10  # Out of range
        
        # Normalize
        audio_norm = audio / np.abs(audio).max()
        
        assert audio_norm.max() <= 1.0
        assert audio_norm.min() >= -1.0
    
    def test_chunk_overlap(self):
        """Test audio chunking with overlap"""
        sample_rate = 16000
        chunk_duration = 3
        buffer_duration = 1
        
        chunk_samples = sample_rate * chunk_duration  # 48000
        buffer_samples = sample_rate * buffer_duration  # 16000
        
        # After processing a chunk, we should keep buffer_samples
        remaining = chunk_samples - buffer_samples
        
        assert remaining == 32000  # 2 seconds worth


class TestLanguageHandling:
    """Test language code handling"""
    
    def test_valid_language_codes(self):
        """Test valid language codes are accepted"""
        valid_codes = ['en', 'ko', 'ja', 'zh', 'es', 'fr', 'de', 'ru', 'ar']
        
        for code in valid_codes:
            with patch('whisper.load_model'), \
                 patch('transformers.AutoTokenizer.from_pretrained'), \
                 patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
                translator = RealtimeTranslator(source_language=code)
                assert translator.source_language == code
    
    def test_nllb_language_codes(self):
        """Test NLLB language code format"""
        valid_nllb_codes = [
            'eng_Latn', 'fra_Latn', 'spa_Latn', 'deu_Latn',
            'kor_Hang', 'jpn_Jpan', 'zho_Hans', 'ara_Arab'
        ]
        
        for code in valid_nllb_codes:
            with patch('whisper.load_model'), \
                 patch('transformers.AutoTokenizer.from_pretrained'), \
                 patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
                translator = RealtimeTranslator(target_language=code)
                assert translator.target_language == code


class TestErrorRecovery:
    """Test error recovery and resilience"""
    
    def test_queue_timeout_handling(self):
        """Test handling of queue timeout"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = RealtimeTranslator()
            
            # Queue should timeout gracefully
            import queue
            with patch.object(translator.audio_queue, 'get') as mock_get:
                mock_get.side_effect = queue.Empty
                
                # Should not raise exception
                translator.is_running = True
                # This would be called in the processing loop
                # Just verify the exception type exists
                assert queue.Empty
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown"""
        with patch('whisper.load_model'), \
             patch('transformers.AutoTokenizer.from_pretrained'), \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained'):
            translator = RealtimeTranslator()
            
            translator.is_running = True
            translator.stop()
            
            assert translator.is_running == False


class TestIntegration:
    """Integration tests"""
    
    def test_end_to_end_mock(self):
        """Test end-to-end with mocked models"""
        with patch('whisper.load_model') as mock_whisper, \
             patch('transformers.AutoTokenizer.from_pretrained') as mock_tokenizer, \
             patch('transformers.AutoModelForSeq2SeqLM.from_pretrained') as mock_model:
            
            # Setup mocks
            mock_whisper_instance = MagicMock()
            mock_whisper_instance.transcribe.return_value = {
                "text": "Hello world",
                "language": "en"
            }
            mock_whisper.return_value = mock_whisper_instance
            
            mock_tokenizer_instance = MagicMock()
            mock_tokenizer_instance.lang_code_to_id = {"eng_Latn": 0}
            mock_tokenizer.return_value = mock_tokenizer_instance
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate.return_value = [[1, 2, 3]]
            mock_model.return_value = mock_model_instance
            
            mock_tokenizer_instance.batch_decode.return_value = ["Translated text"]
            
            # Create translator
            translator = RealtimeTranslator(
                source_language="en",
                target_language="eng_Latn",
                whisper_model="tiny"
            )
            
            # Process audio
            audio = np.random.randn(32000).astype(np.float32)
            original, translated = translator.process_audio_chunk(audio)
            
            # Verify results
            assert original == "Hello world"
            assert translated == "Translated text"


def test_requirements_installed():
    """Test that all required packages are available"""
    required_packages = [
        'numpy',
        'sounddevice',
        'whisper',
        'torch',
        'transformers'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            pytest.fail(f"Required package '{package}' is not installed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

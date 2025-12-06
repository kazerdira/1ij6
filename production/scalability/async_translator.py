#!/usr/bin/env python3
"""
Async Real-time Translator
Non-blocking async implementation for handling concurrent requests
WITH CIRCUIT BREAKERS AND RETRY LOGIC
"""

import asyncio
import numpy as np
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Handle imports gracefully
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Import circuit breaker and retry
from reliability.circuit_breaker import async_circuit_breaker, CircuitBreakerError
from reliability.retry_handler import async_retry, RetryExhausted


class AsyncRealtimeTranslator:
    """
    Async translator that can handle multiple requests concurrently
    Uses thread pool for CPU-bound operations (model inference)
    WITH CIRCUIT BREAKERS AND RETRY LOGIC
    """
    
    def __init__(
        self,
        source_language: str = "ko",
        target_language: str = "eng_Latn",
        whisper_model: str = "base",
        max_workers: int = 4
    ):
        """
        Initialize async translator
        
        Args:
            source_language: Source language code
            target_language: Target language code  
            whisper_model: Whisper model size
            max_workers: Max concurrent workers for model inference
        """
        self.source_language = source_language
        self.target_language = target_language
        self.whisper_model_name = whisper_model
        
        # Thread pool for CPU-bound model operations
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Models (loaded lazily)
        self.whisper_model = None
        self.translator_model = None
        self.translator_tokenizer = None
        
        # Device
        if TORCH_AVAILABLE:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = "cpu"
        
        # Lock for model operations
        self.model_lock = asyncio.Lock()
        
        # Statistics
        self.total_requests = 0
        self.active_requests = 0
        self.max_concurrent_requests = 0
        self.failed_requests = 0
        
        logger.info(f"AsyncRealtimeTranslator initialized on {self.device}")
    
    @async_retry(max_attempts=3, base_delay=2.0, exceptions=(OSError, RuntimeError, ConnectionError))
    async def load_models(self):
        """Load models asynchronously WITH RETRY LOGIC"""
        if self.whisper_model is not None and self.translator_model is not None:
            return  # Already loaded
        
        if not WHISPER_AVAILABLE or not TRANSFORMERS_AVAILABLE:
            raise ImportError("whisper and transformers are required")
        
        async with self.model_lock:
            # Double-check after acquiring lock
            if self.whisper_model is not None and self.translator_model is not None:
                return
            
            logger.info("Loading models with retry protection...")
            
            loop = asyncio.get_event_loop()
            
            try:
                # Load Whisper
                logger.info(f"Loading Whisper model: {self.whisper_model_name}")
                self.whisper_model = await loop.run_in_executor(
                    self.executor,
                    whisper.load_model,
                    self.whisper_model_name
                )
                logger.info("✅ Whisper model loaded")
                
                # Load translator
                model_name = "facebook/nllb-200-distilled-600M"
                
                logger.info(f"Loading NLLB tokenizer...")
                self.translator_tokenizer = await loop.run_in_executor(
                    self.executor,
                    AutoTokenizer.from_pretrained,
                    model_name
                )
                logger.info("✅ NLLB tokenizer loaded")
                
                logger.info(f"Loading NLLB model...")
                self.translator_model = await loop.run_in_executor(
                    self.executor,
                    AutoModelForSeq2SeqLM.from_pretrained,
                    model_name
                )
                logger.info("✅ NLLB model loaded")
                
                # Move to GPU if available
                if self.device == "cuda" and TORCH_AVAILABLE:
                    logger.info("Moving model to GPU...")
                    self.translator_model = self.translator_model.to(self.device)
                
                logger.info("✅ All models loaded successfully")
            
            except Exception as e:
                logger.error(f"Error loading models: {e}")
                self.whisper_model = None
                self.translator_model = None
                self.translator_tokenizer = None
                raise
    
    @async_circuit_breaker(failure_threshold=5, recovery_timeout=60, name="whisper_transcribe")
    async def transcribe_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio asynchronously WITH CIRCUIT BREAKER
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            Transcribed text
        """
        await self.load_models()
        
        # Normalize audio
        audio_float = audio_data.astype(np.float32)
        if audio_float.max() > 1.0 or audio_float.min() < -1.0:
            max_val = np.abs(audio_float).max()
            if max_val > 0:
                audio_float = audio_float / max_val
        
        loop = asyncio.get_event_loop()
        
        def _transcribe():
            try:
                result = self.whisper_model.transcribe(
                    audio_float,
                    language=self.source_language,
                    task="transcribe",
                    fp16=False
                )
                return result["text"].strip()
            except Exception as e:
                logger.error(f"Whisper transcription error: {e}")
                raise
        
        transcribed_text = await loop.run_in_executor(
            self.executor,
            _transcribe
        )
        
        return transcribed_text
    
    @async_circuit_breaker(failure_threshold=5, recovery_timeout=60, name="nllb_translate")
    async def translate_text(self, text: str, source_language: str = None, target_language: str = None) -> str:
        """
        Translate text asynchronously WITH CIRCUIT BREAKER
        
        Args:
            text: Text to translate
            source_language: Source language code (optional, uses default if not provided)
            target_language: Target language code (optional, uses default if not provided)
        
        Returns:
            Translated text
        """
        await self.load_models()
        
        if not text:
            return ""
        
        # Use provided languages or fall back to defaults
        src_lang = source_language or self.source_language
        tgt_lang = target_language or self.target_language
        
        loop = asyncio.get_event_loop()
        
        def _translate():
            try:
                inputs = self.translator_tokenizer(
                    text,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                )
                
                if self.device == "cuda" and TORCH_AVAILABLE:
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(
                    tgt_lang
                )
                
                with torch.no_grad():
                    translated_tokens = self.translator_model.generate(
                        **inputs,
                        forced_bos_token_id=target_lang_id,
                        max_length=512,
                        num_beams=5,
                        early_stopping=True
                    )
                
                translated_text = self.translator_tokenizer.batch_decode(
                    translated_tokens,
                    skip_special_tokens=True
                )[0]
                
                return translated_text
            
            except Exception as e:
                logger.error(f"Translation error: {e}")
                raise
        
        translated_text = await loop.run_in_executor(
            self.executor,
            _translate
        )
        
        return translated_text
    
    async def process_audio(self, audio_data: np.ndarray) -> Tuple[str, str]:
        """
        Process audio: transcribe and translate
        WITH ERROR HANDLING FOR CIRCUIT BREAKERS
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            (original_text, translated_text)
        """
        self.active_requests += 1
        self.total_requests += 1
        self.max_concurrent_requests = max(
            self.max_concurrent_requests,
            self.active_requests
        )
        
        try:
            # Transcribe with circuit breaker
            try:
                original = await self.transcribe_audio(audio_data)
            except CircuitBreakerError:
                logger.error("Transcription circuit breaker open")
                self.failed_requests += 1
                raise
            except RetryExhausted:
                logger.error("Transcription retry exhausted")
                self.failed_requests += 1
                raise
            
            if not original:
                return "", ""
            
            # Translate with circuit breaker
            try:
                translated = await self.translate_text(original)
            except CircuitBreakerError:
                logger.error("Translation circuit breaker open")
                self.failed_requests += 1
                return original, ""  # Return transcription only
            except RetryExhausted:
                logger.error("Translation retry exhausted")
                self.failed_requests += 1
                return original, ""
            
            return original, translated
        
        except (CircuitBreakerError, RetryExhausted):
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.failed_requests += 1
            raise
        finally:
            self.active_requests -= 1
    
    async def process_audio_batch(self, audio_list: list) -> list:
        """
        Process multiple audio samples concurrently
        
        Args:
            audio_list: List of audio numpy arrays
        
        Returns:
            List of (original, translated) tuples
        """
        tasks = [self.process_audio(audio) for audio in audio_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing audio {i}: {result}")
                processed_results.append(("", ""))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> dict:
        """Get translator statistics"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.failed_requests) / self.total_requests) * 100
        
        return {
            'total_requests': self.total_requests,
            'active_requests': self.active_requests,
            'max_concurrent_requests': self.max_concurrent_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(success_rate, 2),
            'device': self.device,
            'models_loaded': self.whisper_model is not None
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down translator...")
        self.executor.shutdown(wait=True)
        
        if self.device == "cuda" and TORCH_AVAILABLE:
            try:
                torch.cuda.empty_cache()
                logger.info("GPU memory cleared")
            except Exception as e:
                logger.error(f"Error clearing GPU: {e}")
        
        logger.info("AsyncRealtimeTranslator cleaned up")

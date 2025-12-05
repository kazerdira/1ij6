#!/usr/bin/env python3
"""
Async Real-time Translator
Non-blocking async implementation for handling concurrent requests
"""

import asyncio
import numpy as np
import torch
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import whisper
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import logging

logger = logging.getLogger(__name__)


class AsyncRealtimeTranslator:
    """
    Async translator that can handle multiple requests concurrently
    Uses thread pool for CPU-bound operations (model inference)
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
        self.whisper_model: Optional[whisper.Whisper] = None
        self.translator_model: Optional[AutoModelForSeq2SeqLM] = None
        self.translator_tokenizer: Optional[AutoTokenizer] = None
        
        # Device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Lock for model operations
        self.model_lock = asyncio.Lock()
        
        # Statistics
        self.total_requests = 0
        self.active_requests = 0
        self.max_concurrent_requests = 0
        
        logger.info(f"AsyncRealtimeTranslator initialized on {self.device}")
    
    async def load_models(self):
        """Load models asynchronously"""
        if self.whisper_model is not None and self.translator_model is not None:
            return  # Already loaded
        
        async with self.model_lock:
            # Double-check after acquiring lock
            if self.whisper_model is not None and self.translator_model is not None:
                return
            
            logger.info("Loading models...")
            
            # Load in thread pool (blocking operations)
            loop = asyncio.get_event_loop()
            
            # Load Whisper
            self.whisper_model = await loop.run_in_executor(
                self.executor,
                whisper.load_model,
                self.whisper_model_name
            )
            
            # Load translator
            model_name = "facebook/nllb-200-distilled-600M"
            
            self.translator_tokenizer = await loop.run_in_executor(
                self.executor,
                AutoTokenizer.from_pretrained,
                model_name
            )
            
            self.translator_model = await loop.run_in_executor(
                self.executor,
                AutoModelForSeq2SeqLM.from_pretrained,
                model_name
            )
            
            # Move to GPU if available
            if self.device == "cuda":
                self.translator_model = self.translator_model.to(self.device)
            
            logger.info("Models loaded successfully")
    
    async def transcribe_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio asynchronously
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            Transcribed text
        """
        # Ensure models are loaded
        await self.load_models()
        
        # Normalize audio
        audio_float = audio_data.astype(np.float32)
        if audio_float.max() > 1.0 or audio_float.min() < -1.0:
            audio_float = audio_float / np.abs(audio_float).max()
        
        # Run transcription in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        
        def _transcribe():
            result = self.whisper_model.transcribe(
                audio_float,
                language=self.source_language,
                task="transcribe",
                fp16=False
            )
            return result["text"].strip()
        
        transcribed_text = await loop.run_in_executor(
            self.executor,
            _transcribe
        )
        
        return transcribed_text
    
    async def translate_text(self, text: str) -> str:
        """
        Translate text asynchronously
        
        Args:
            text: Text to translate
        
        Returns:
            Translated text
        """
        # Ensure models are loaded
        await self.load_models()
        
        if not text:
            return ""
        
        # Run translation in thread pool
        loop = asyncio.get_event_loop()
        
        def _translate():
            # Tokenize
            inputs = self.translator_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # Move to GPU if available
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get target language token ID
            target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(
                self.target_language
            )
            
            # Generate translation
            with torch.no_grad():
                translated_tokens = self.translator_model.generate(
                    **inputs,
                    forced_bos_token_id=target_lang_id,
                    max_length=512,
                    num_beams=5,
                    early_stopping=True
                )
            
            # Decode
            translated_text = self.translator_tokenizer.batch_decode(
                translated_tokens,
                skip_special_tokens=True
            )[0]
            
            return translated_text
        
        translated_text = await loop.run_in_executor(
            self.executor,
            _translate
        )
        
        return translated_text
    
    async def process_audio(self, audio_data: np.ndarray) -> Tuple[str, str]:
        """
        Process audio: transcribe and translate
        
        Args:
            audio_data: Audio numpy array
        
        Returns:
            (original_text, translated_text)
        """
        # Track concurrent requests
        self.active_requests += 1
        self.total_requests += 1
        self.max_concurrent_requests = max(
            self.max_concurrent_requests,
            self.active_requests
        )
        
        try:
            # Transcribe
            original = await self.transcribe_audio(audio_data)
            
            if not original:
                return "", ""
            
            # Translate
            translated = await self.translate_text(original)
            
            return original, translated
        
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
        
        # Handle exceptions
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
        return {
            'total_requests': self.total_requests,
            'active_requests': self.active_requests,
            'max_concurrent_requests': self.max_concurrent_requests,
            'device': self.device,
            'models_loaded': self.whisper_model is not None
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        
        # Clear GPU memory
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        logger.info("AsyncRealtimeTranslator cleaned up")


# Example usage:
"""
import asyncio
from scalability.async_translator import AsyncRealtimeTranslator

async def main():
    translator = AsyncRealtimeTranslator(
        source_language="ko",
        target_language="eng_Latn",
        whisper_model="base",
        max_workers=4
    )
    
    # Load models
    await translator.load_models()
    
    # Process single audio
    import numpy as np
    audio = np.random.randn(48000).astype(np.float32)
    original, translated = await translator.process_audio(audio)
    print(f"Original: {original}")
    print(f"Translated: {translated}")
    
    # Process batch
    audio_batch = [np.random.randn(48000).astype(np.float32) for _ in range(10)]
    results = await translator.process_audio_batch(audio_batch)
    
    # Cleanup
    await translator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
"""

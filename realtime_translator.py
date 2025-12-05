#!/usr/bin/env python3
"""
Real-time Speech Transcription and Translation System
Uses OpenAI Whisper for speech-to-text and Meta's NLLB for translation
Completely free and offline solution
"""

import numpy as np
import sounddevice as sd
import queue
import threading
import time
from datetime import datetime
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import whisper
import sys
from collections import deque


class RealtimeTranslator:
    """Production-grade real-time audio transcription and translation"""
    
    def __init__(
        self,
        source_language="ko",  # Korean
        target_language="eng_Latn",  # English
        whisper_model="base",  # Options: tiny, base, small, medium, large
        sample_rate=16000,
        chunk_duration=3,  # seconds
        buffer_duration=1  # seconds of overlap
    ):
        """
        Initialize the translator
        
        Args:
            source_language: Source language code (ko, ja, zh, etc.)
            target_language: Target language code for NLLB (eng_Latn, fra_Latn, etc.)
            whisper_model: Whisper model size (tiny, base, small, medium, large)
            sample_rate: Audio sample rate in Hz
            chunk_duration: Duration of audio chunks to process
            buffer_duration: Overlap duration for better continuity
        """
        print("🚀 Initializing Real-time Translator...")
        print(f"   Source: {source_language} → Target: {target_language}")
        
        self.source_language = source_language
        self.target_language = target_language
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.buffer_duration = buffer_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        self.buffer_samples = int(sample_rate * buffer_duration)
        
        # Audio queue for real-time processing
        self.audio_queue = queue.Queue()
        self.is_running = False
        
        # Audio buffer with overlap
        self.audio_buffer = deque(maxlen=self.chunk_samples + self.buffer_samples)
        
        # Load models
        self._load_whisper(whisper_model)
        self._load_translator()
        
        # Statistics
        self.transcription_count = 0
        self.translation_count = 0
        self.start_time = None
        
        print("✅ Initialization complete!\n")
    
    def _load_whisper(self, model_size):
        """Load Whisper model for speech recognition"""
        print(f"📥 Loading Whisper model ({model_size})...")
        try:
            self.whisper_model = whisper.load_model(model_size)
            # Check if CUDA is available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"   Device: {self.device.upper()}")
            print("✅ Whisper loaded successfully")
        except Exception as e:
            print(f"❌ Error loading Whisper: {e}")
            sys.exit(1)
    
    def _load_translator(self):
        """Load NLLB translation model"""
        print("📥 Loading NLLB translation model...")
        print("   (This may take a moment on first run...)")
        try:
            model_name = "facebook/nllb-200-distilled-600M"
            self.translator_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.translator_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            # Move to GPU if available
            if torch.cuda.is_available():
                self.translator_model = self.translator_model.to("cuda")
            
            print("✅ NLLB translator loaded successfully")
        except Exception as e:
            print(f"❌ Error loading translator: {e}")
            print("   Installing transformers and sentencepiece may help:")
            print("   pip install transformers sentencepiece")
            sys.exit(1)
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream - called by sounddevice"""
        if status:
            print(f"⚠️  Audio status: {status}", file=sys.stderr)
        
        # Convert to mono if stereo
        if len(indata.shape) > 1:
            audio_data = indata[:, 0]
        else:
            audio_data = indata.copy()
        
        # Add to queue
        self.audio_queue.put(audio_data)
    
    def process_audio_chunk(self, audio_chunk):
        """Process audio chunk: transcribe and translate"""
        try:
            # Transcribe with Whisper
            audio_float = audio_chunk.astype(np.float32)
            
            # Whisper expects audio normalized to [-1, 1]
            if audio_float.max() > 1.0 or audio_float.min() < -1.0:
                audio_float = audio_float / np.abs(audio_float).max()
            
            # Transcribe
            result = self.whisper_model.transcribe(
                audio_float,
                language=self.source_language,
                task="transcribe",
                fp16=False  # Use fp16=True if you have CUDA
            )
            
            transcribed_text = result["text"].strip()
            
            if not transcribed_text:
                return None, None
            
            self.transcription_count += 1
            
            # Translate
            translated_text = self.translate_text(transcribed_text)
            self.translation_count += 1
            
            return transcribed_text, translated_text
            
        except Exception as e:
            print(f"❌ Error processing audio: {e}")
            return None, None
    
    def translate_text(self, text):
        """Translate text using NLLB"""
        try:
            # Tokenize with source language
            inputs = self.translator_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            # Move to GPU if available
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Get target language token ID (compatible with newer tokenizers)
            target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(self.target_language)
            
            # Generate translation
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
            
        except Exception as e:
            print(f"❌ Translation error: {e}")
            return "[Translation Error]"
    
    def process_audio_stream(self):
        """Main processing loop - runs in separate thread"""
        print("\n🎙️  Listening... (Press Ctrl+C to stop)\n")
        self.start_time = time.time()
        
        while self.is_running:
            try:
                # Get audio from queue with timeout
                audio_data = self.audio_queue.get(timeout=0.1)
                
                # Add to rolling buffer
                self.audio_buffer.extend(audio_data)
                
                # Process when we have enough audio
                if len(self.audio_buffer) >= self.chunk_samples:
                    # Get audio chunk from buffer
                    audio_chunk = np.array(list(self.audio_buffer)[:self.chunk_samples])
                    
                    # Process the chunk
                    original, translated = self.process_audio_chunk(audio_chunk)
                    
                    if original and translated:
                        # Display results
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}]")
                        print(f"🗣️  Original ({self.source_language}): {original}")
                        print(f"💬 Translated: {translated}")
                        print("-" * 80)
                    
                    # Remove processed samples, keep buffer overlap
                    for _ in range(self.chunk_samples - self.buffer_samples):
                        if len(self.audio_buffer) > 0:
                            self.audio_buffer.popleft()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Processing error: {e}")
                continue
    
    def start(self):
        """Start the real-time translator"""
        self.is_running = True
        
        # Start processing thread
        processing_thread = threading.Thread(target=self.process_audio_stream, daemon=True)
        processing_thread.start()
        
        try:
            # Start audio stream
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self.audio_callback,
                blocksize=int(self.sample_rate * 0.1),  # 100ms blocks
                dtype=np.float32
            ):
                # Keep running until interrupted
                while self.is_running:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping translator...")
            self.stop()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.stop()
    
    def stop(self):
        """Stop the translator and show statistics"""
        self.is_running = False
        
        if self.start_time:
            duration = time.time() - self.start_time
            print("\n" + "=" * 80)
            print("📊 Session Statistics:")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Transcriptions: {self.transcription_count}")
            print(f"   Translations: {self.translation_count}")
            print("=" * 80)
        
        print("\n👋 Goodbye!")


def main():
    """Main entry point"""
    print("=" * 80)
    print("  Real-time Speech Translator - Whisper + NLLB")
    print("  Free & Offline Solution")
    print("=" * 80)
    print()
    
    # Configuration
    # Language codes for NLLB: https://github.com/facebookresearch/flores/blob/main/flores200/README.md#languages-in-flores-200
    config = {
        "source_language": "ko",  # Korean (change to: ja, zh, fr, es, etc.)
        "target_language": "eng_Latn",  # English (change to: fra_Latn, spa_Latn, etc.)
        "whisper_model": "base",  # Options: tiny, base, small, medium, large
        "chunk_duration": 3,  # Process every 3 seconds
        "buffer_duration": 1,  # 1 second overlap for continuity
    }
    
    print("⚙️  Configuration:")
    print(f"   Source Language: {config['source_language']}")
    print(f"   Target Language: {config['target_language']}")
    print(f"   Whisper Model: {config['whisper_model']}")
    print(f"   Chunk Duration: {config['chunk_duration']}s")
    print()
    
    # Create and start translator
    translator = RealtimeTranslator(**config)
    translator.start()


if __name__ == "__main__":
    main()

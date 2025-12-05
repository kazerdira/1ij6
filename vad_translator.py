#!/usr/bin/env python3
"""
Real-time Speech Translator with Voice Activity Detection (VAD)
Skips silence to improve performance and reduce unnecessary processing
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
import os
from collections import deque
import logging
from typing import Optional, Tuple

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    print("⚠️  WebRTC VAD not available. Install with: pip install webrtcvad")
    print("   Continuing without voice activity detection...")


class VADRealtimeTranslator:
    """
    Enhanced real-time translator with Voice Activity Detection
    Skips silent audio to save processing power
    """
    
    def __init__(
        self,
        source_language="ko",
        target_language="eng_Latn",
        whisper_model="base",
        sample_rate=16000,
        chunk_duration=3,
        buffer_duration=1,
        vad_aggressiveness=3,
        vad_frame_duration=30,  # ms
        silence_threshold=0.5,   # seconds of silence before skipping
        log_file=None,
        verbose=True
    ):
        """
        Initialize VAD-enhanced translator
        
        Args:
            vad_aggressiveness: VAD sensitivity (0-3, higher = more aggressive)
            vad_frame_duration: VAD frame size in milliseconds (10, 20, or 30)
            silence_threshold: Seconds of continuous silence before skipping
            log_file: Path to log file (None for console only)
            verbose: Enable verbose logging
        """
        # Setup logging
        self._setup_logging(log_file, verbose)
        
        self.logger.info("🚀 Initializing VAD-Enhanced Real-time Translator...")
        self.logger.info(f"   Source: {source_language} → Target: {target_language}")
        
        self.source_language = source_language
        self.target_language = target_language
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.buffer_duration = buffer_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        self.buffer_samples = int(sample_rate * buffer_duration)
        
        # VAD settings
        self.vad_enabled = VAD_AVAILABLE
        self.vad_aggressiveness = vad_aggressiveness
        self.vad_frame_duration = vad_frame_duration
        self.silence_threshold = silence_threshold
        
        # Initialize VAD
        if self.vad_enabled:
            self.vad = webrtcvad.Vad(vad_aggressiveness)
            self.vad_frame_samples = int(sample_rate * vad_frame_duration / 1000)
            self.logger.info(f"   VAD: Enabled (aggressiveness={vad_aggressiveness})")
        else:
            self.vad = None
            self.logger.info("   VAD: Disabled")
        
        # Audio processing
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.audio_buffer = deque(maxlen=self.chunk_samples + self.buffer_samples)
        
        # Voice activity tracking
        self.silence_duration = 0
        self.is_speaking = False
        self.speech_start_time = None
        
        # Load models
        self._load_whisper(whisper_model)
        self._load_translator()
        
        # Statistics
        self.transcription_count = 0
        self.translation_count = 0
        self.error_count = 0
        self.chunks_skipped = 0
        self.chunks_processed = 0
        self.start_time = None
        
        self.logger.info("✅ Initialization complete!\n")
    
    def _setup_logging(self, log_file, verbose):
        """Setup logging configuration"""
        self.logger = logging.getLogger('VADTranslator')
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Clear existing handlers
        self.logger.handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
            self.logger.info(f"Logging to file: {log_file}")
    
    def _load_whisper(self, model_size):
        """Load Whisper model"""
        self.logger.info(f"📥 Loading Whisper model ({model_size})...")
        try:
            self.whisper_model = whisper.load_model(model_size)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.logger.info(f"   Device: {self.device.upper()}")
            self.logger.info("✅ Whisper loaded successfully")
        except Exception as e:
            self.logger.error(f"❌ Error loading Whisper: {e}")
            sys.exit(1)
    
    def _load_translator(self):
        """Load NLLB translation model"""
        self.logger.info("📥 Loading NLLB translation model...")
        try:
            model_name = "facebook/nllb-200-distilled-600M"
            self.translator_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.translator_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            if torch.cuda.is_available():
                self.translator_model = self.translator_model.to("cuda")
            
            self.logger.info("✅ NLLB translator loaded successfully")
        except Exception as e:
            self.logger.error(f"❌ Error loading translator: {e}")
            sys.exit(1)
    
    def is_speech(self, audio_frame: np.ndarray) -> bool:
        """
        Check if audio frame contains speech using VAD
        
        Args:
            audio_frame: Audio frame (must be 10, 20, or 30 ms at 16kHz)
        
        Returns:
            True if speech detected, False otherwise
        """
        if not self.vad_enabled:
            return True  # Process everything if VAD not available
        
        try:
            # Convert float32 to int16 for VAD
            audio_int16 = (audio_frame * 32768).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # Check for speech
            return self.vad.is_speech(audio_bytes, self.sample_rate)
        except Exception as e:
            self.logger.debug(f"VAD error: {e}")
            return True  # Default to processing on error
    
    def detect_voice_activity(self, audio_chunk: np.ndarray) -> bool:
        """
        Analyze audio chunk for voice activity
        
        Args:
            audio_chunk: Audio data to analyze
        
        Returns:
            True if speech detected, False if silence
        """
        if not self.vad_enabled:
            return True
        
        # Analyze chunk in VAD frames
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(audio_chunk) - self.vad_frame_samples, self.vad_frame_samples):
            frame = audio_chunk[i:i + self.vad_frame_samples]
            
            if len(frame) == self.vad_frame_samples:
                total_frames += 1
                if self.is_speech(frame):
                    speech_frames += 1
        
        if total_frames == 0:
            return True
        
        # Consider it speech if more than 30% of frames contain speech
        speech_ratio = speech_frames / total_frames
        return speech_ratio > 0.3
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream"""
        if status:
            self.logger.warning(f"⚠️  Audio status: {status}")
        
        # Convert to mono
        if len(indata.shape) > 1:
            audio_data = indata[:, 0]
        else:
            audio_data = indata.copy()
        
        self.audio_queue.put(audio_data)
    
    def process_audio_chunk(self, audio_chunk: np.ndarray) -> Tuple[Optional[str], Optional[str]]:
        """Process audio chunk: transcribe and translate"""
        try:
            # Check for voice activity
            has_speech = self.detect_voice_activity(audio_chunk)
            
            if not has_speech:
                self.silence_duration += self.chunk_duration
                
                if self.silence_duration >= self.silence_threshold:
                    self.chunks_skipped += 1
                    self.logger.debug(f"Skipping silent chunk ({self.silence_duration:.1f}s silence)")
                    
                    if self.is_speaking:
                        self.is_speaking = False
                        self.logger.debug("Speech ended")
                    
                    return None, None
            else:
                # Speech detected
                if not self.is_speaking:
                    self.is_speaking = True
                    self.speech_start_time = time.time()
                    self.logger.debug("Speech started")
                
                self.silence_duration = 0
            
            # Normalize audio
            audio_float = audio_chunk.astype(np.float32)
            if audio_float.max() > 1.0 or audio_float.min() < -1.0:
                audio_float = audio_float / np.abs(audio_float).max()
            
            # Transcribe
            result = self.whisper_model.transcribe(
                audio_float,
                language=self.source_language,
                task="transcribe",
                fp16=False
            )
            
            transcribed_text = result["text"].strip()
            
            if not transcribed_text:
                return None, None
            
            self.transcription_count += 1
            self.chunks_processed += 1
            
            # Translate
            translated_text = self.translate_text(transcribed_text)
            self.translation_count += 1
            
            return transcribed_text, translated_text
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Error processing audio: {e}")
            return None, None
    
    def translate_text(self, text: str) -> str:
        """Translate text using NLLB"""
        try:
            inputs = self.translator_tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # Get target language token ID (compatible with newer tokenizers)
            target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(self.target_language)
            
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
            self.logger.error(f"❌ Translation error: {e}")
            return "[Translation Error]"
    
    def process_audio_stream(self):
        """Main processing loop"""
        self.logger.info("\n🎙️  Listening with VAD... (Press Ctrl+C to stop)\n")
        if self.vad_enabled:
            self.logger.info("💡 VAD is active - silent periods will be skipped automatically\n")
        
        self.start_time = time.time()
        
        while self.is_running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                
                self.audio_buffer.extend(audio_data)
                
                if len(self.audio_buffer) >= self.chunk_samples:
                    audio_chunk = np.array(list(self.audio_buffer)[:self.chunk_samples])
                    
                    original, translated = self.process_audio_chunk(audio_chunk)
                    
                    if original and translated:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}]")
                        print(f"🗣️  Original ({self.source_language}): {original}")
                        print(f"💬 Translated: {translated}")
                        print("-" * 80)
                    
                    # Remove processed samples
                    for _ in range(self.chunk_samples - self.buffer_samples):
                        if len(self.audio_buffer) > 0:
                            self.audio_buffer.popleft()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"❌ Processing error: {e}")
                continue
    
    def start(self):
        """Start the translator"""
        self.is_running = True
        
        processing_thread = threading.Thread(target=self.process_audio_stream, daemon=True)
        processing_thread.start()
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self.audio_callback,
                blocksize=int(self.sample_rate * 0.1),
                dtype=np.float32
            ):
                while self.is_running:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            self.logger.info("\n\n🛑 Stopping translator...")
            self.stop()
        except Exception as e:
            self.logger.error(f"\n❌ Error: {e}")
            self.stop()
    
    def stop(self):
        """Stop the translator and show statistics"""
        self.is_running = False
        
        if self.start_time:
            duration = time.time() - self.start_time
            total_chunks = self.chunks_processed + self.chunks_skipped
            
            self.logger.info("\n" + "=" * 80)
            self.logger.info("📊 Session Statistics:")
            self.logger.info(f"   Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            self.logger.info(f"   Transcriptions: {self.transcription_count}")
            self.logger.info(f"   Translations: {self.translation_count}")
            self.logger.info(f"   Errors: {self.error_count}")
            
            if self.vad_enabled and total_chunks > 0:
                skip_percent = (self.chunks_skipped / total_chunks) * 100
                self.logger.info(f"   Chunks Processed: {self.chunks_processed}")
                self.logger.info(f"   Chunks Skipped (VAD): {self.chunks_skipped} ({skip_percent:.1f}%)")
                self.logger.info(f"   💡 VAD saved ~{skip_percent:.1f}% processing time!")
            
            if self.transcription_count > 0:
                avg_time = duration / self.transcription_count
                self.logger.info(f"   Average Time per Transcription: {avg_time:.2f}s")
            
            self.logger.info("=" * 80)
        
        self.logger.info("\n👋 Goodbye!")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="VAD-Enhanced Real-time Speech Translator"
    )
    parser.add_argument("--source", "-s", default="ko", help="Source language")
    parser.add_argument("--target", "-t", default="eng_Latn", help="Target language")
    parser.add_argument("--model", "-m", default="base", help="Whisper model size")
    parser.add_argument("--vad", type=int, default=3, choices=[0, 1, 2, 3],
                       help="VAD aggressiveness (0-3, higher = more aggressive)")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("  VAD-Enhanced Real-time Speech Translator")
    print("  Whisper + NLLB + Voice Activity Detection")
    print("=" * 80)
    print()
    
    if args.no_vad or not VAD_AVAILABLE:
        print("⚠️  VAD disabled - all audio will be processed")
        vad_aggressiveness = 0
    else:
        vad_aggressiveness = args.vad
    
    translator = VADRealtimeTranslator(
        source_language=args.source,
        target_language=args.target,
        whisper_model=args.model,
        vad_aggressiveness=vad_aggressiveness if not args.no_vad else None,
        log_file=args.log,
        verbose=args.verbose
    )
    
    translator.start()


if __name__ == "__main__":
    main()

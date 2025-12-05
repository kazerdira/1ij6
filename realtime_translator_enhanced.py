#!/usr/bin/env python3
"""
Real-time Speech Transcription and Translation System - Enhanced Version
Uses OpenAI Whisper for speech-to-text and Meta's NLLB for translation
Supports configuration files and advanced features
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
import configparser
import argparse
import json


class EnhancedRealtimeTranslator:
    """Enhanced production-grade real-time audio transcription and translation"""
    
    def __init__(self, config_file=None, **kwargs):
        """
        Initialize the translator
        
        Args:
            config_file: Path to configuration file (optional)
            **kwargs: Override configuration parameters
        """
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Override with kwargs if provided
        for key, value in kwargs.items():
            if value is not None:
                self.config[key] = value
        
        print("🚀 Initializing Enhanced Real-time Translator...")
        self._print_config()
        
        # Audio processing
        self.sample_rate = self.config.get("sample_rate", 16000)
        self.chunk_duration = self.config.get("chunk_duration", 3)
        self.buffer_duration = self.config.get("buffer_duration", 1)
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
        self.buffer_samples = int(self.sample_rate * self.buffer_duration)
        
        # Audio queue and buffer
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.audio_buffer = deque(maxlen=self.chunk_samples + self.buffer_samples)
        
        # File output
        self.save_to_file = self.config.get("save_to_file", False)
        self.output_file = self.config.get("output_file", "transcriptions.txt")
        if self.save_to_file:
            self.file_handle = open(self.output_file, "a", encoding="utf-8")
        else:
            self.file_handle = None
        
        # Load models
        self._load_whisper()
        self._load_translator()
        
        # Statistics
        self.transcription_count = 0
        self.translation_count = 0
        self.error_count = 0
        self.start_time = None
        self.total_audio_processed = 0
        
        print("✅ Initialization complete!\n")
    
    def _load_config(self, config_file):
        """Load configuration from file or use defaults"""
        config = {
            # General
            "verbose": True,
            "save_to_file": False,
            "output_file": "transcriptions.txt",
            
            # Audio
            "sample_rate": 16000,
            "chunk_duration": 3,
            "buffer_duration": 1,
            "audio_device": -1,
            
            # Whisper
            "whisper_model": "base",
            "source_language": "ko",
            
            # Translation
            "target_language": "eng_Latn",
            "nllb_model": "facebook/nllb-200-distilled-600M",
            "num_beams": 5,
            
            # Performance
            "use_gpu": True,
            "fp16": False,
            
            # Display
            "show_timestamp": True,
            "show_language": True,
            "max_display_length": 0,
            "color_output": False,
        }
        
        if config_file and os.path.exists(config_file):
            print(f"📄 Loading configuration from: {config_file}")
            parser = configparser.ConfigParser()
            parser.read(config_file)
            
            # Parse config sections
            if "Audio" in parser:
                config["sample_rate"] = parser.getint("Audio", "sample_rate", fallback=16000)
                config["chunk_duration"] = parser.getfloat("Audio", "chunk_duration", fallback=3)
                config["buffer_duration"] = parser.getfloat("Audio", "buffer_duration", fallback=1)
            
            if "Whisper" in parser:
                config["whisper_model"] = parser.get("Whisper", "model_size", fallback="base")
                config["source_language"] = parser.get("Whisper", "source_language", fallback="ko")
            
            if "Translation" in parser:
                config["target_language"] = parser.get("Translation", "target_language", fallback="eng_Latn")
                config["nllb_model"] = parser.get("Translation", "nllb_model", fallback="facebook/nllb-200-distilled-600M")
                config["num_beams"] = parser.getint("Translation", "num_beams", fallback=5)
            
            if "General" in parser:
                config["verbose"] = parser.getboolean("General", "verbose", fallback=True)
                config["save_to_file"] = parser.getboolean("General", "save_to_file", fallback=False)
                config["output_file"] = parser.get("General", "output_file", fallback="transcriptions.txt")
            
            if "Performance" in parser:
                config["use_gpu"] = parser.getboolean("Performance", "use_gpu", fallback=True)
                config["fp16"] = parser.getboolean("Performance", "fp16", fallback=False)
            
            if "Display" in parser:
                config["show_timestamp"] = parser.getboolean("Display", "show_timestamp", fallback=True)
                config["show_language"] = parser.getboolean("Display", "show_language", fallback=True)
                config["max_display_length"] = parser.getint("Display", "max_display_length", fallback=0)
            
            if "Advanced" in parser:
                config["audio_device"] = parser.getint("Advanced", "audio_device", fallback=-1)
        
        return config
    
    def _print_config(self):
        """Print current configuration"""
        print("\n⚙️  Configuration:")
        print(f"   Source Language: {self.config['source_language']}")
        print(f"   Target Language: {self.config['target_language']}")
        print(f"   Whisper Model: {self.config['whisper_model']}")
        print(f"   Chunk Duration: {self.config['chunk_duration']}s")
        print(f"   Sample Rate: {self.config['sample_rate']} Hz")
        if self.config['save_to_file']:
            print(f"   Output File: {self.config['output_file']}")
        print()
    
    def _load_whisper(self):
        """Load Whisper model for speech recognition"""
        print(f"📥 Loading Whisper model ({self.config['whisper_model']})...")
        try:
            self.whisper_model = whisper.load_model(self.config['whisper_model'])
            
            # Check device
            if self.config['use_gpu'] and torch.cuda.is_available():
                self.device = "cuda"
                print(f"   Device: GPU (CUDA)")
            else:
                self.device = "cpu"
                print(f"   Device: CPU")
            
            print("✅ Whisper loaded successfully")
        except Exception as e:
            print(f"❌ Error loading Whisper: {e}")
            print("   Make sure you have installed: pip install openai-whisper")
            sys.exit(1)
    
    def _load_translator(self):
        """Load NLLB translation model"""
        print(f"📥 Loading NLLB translation model...")
        print(f"   Model: {self.config['nllb_model']}")
        print("   (This may take a moment on first run...)")
        
        try:
            self.translator_tokenizer = AutoTokenizer.from_pretrained(self.config['nllb_model'])
            self.translator_model = AutoModelForSeq2SeqLM.from_pretrained(self.config['nllb_model'])
            
            # Move to GPU if available and enabled
            if self.config['use_gpu'] and torch.cuda.is_available():
                self.translator_model = self.translator_model.to("cuda")
                print("   Using GPU for translation")
            
            print("✅ NLLB translator loaded successfully")
        except Exception as e:
            print(f"❌ Error loading translator: {e}")
            print("   Installing transformers and sentencepiece may help:")
            print("   pip install transformers sentencepiece")
            sys.exit(1)
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream"""
        if status and self.config.get("verbose", False):
            print(f"⚠️  Audio status: {status}", file=sys.stderr)
        
        # Convert to mono if stereo
        if len(indata.shape) > 1:
            audio_data = indata[:, 0]
        else:
            audio_data = indata.copy()
        
        self.audio_queue.put(audio_data)
    
    def process_audio_chunk(self, audio_chunk):
        """Process audio chunk: transcribe and translate"""
        try:
            # Prepare audio for Whisper
            audio_float = audio_chunk.astype(np.float32)
            
            # Normalize to [-1, 1]
            if audio_float.max() > 1.0 or audio_float.min() < -1.0:
                audio_float = audio_float / np.abs(audio_float).max()
            
            # Transcribe with Whisper
            result = self.whisper_model.transcribe(
                audio_float,
                language=self.config['source_language'] if self.config['source_language'] != "auto" else None,
                task="transcribe",
                fp16=self.config.get('fp16', False) and self.device == "cuda"
            )
            
            transcribed_text = result["text"].strip()
            
            if not transcribed_text:
                return None, None, None
            
            # Get detected language if auto
            detected_language = result.get("language", self.config['source_language'])
            
            self.transcription_count += 1
            
            # Translate
            translated_text = self.translate_text(transcribed_text)
            self.translation_count += 1
            
            return transcribed_text, translated_text, detected_language
            
        except Exception as e:
            self.error_count += 1
            if self.config.get("verbose", False):
                print(f"❌ Error processing audio: {e}")
            return None, None, None
    
    def translate_text(self, text):
        """Translate text using NLLB"""
        try:
            # Tokenize
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
            target_lang_id = self.translator_tokenizer.convert_tokens_to_ids(self.config['target_language'])
            
            # Generate translation
            translated_tokens = self.translator_model.generate(
                **inputs,
                forced_bos_token_id=target_lang_id,
                max_length=512,
                num_beams=self.config.get('num_beams', 5),
                early_stopping=True
            )
            
            # Decode
            translated_text = self.translator_tokenizer.batch_decode(
                translated_tokens,
                skip_special_tokens=True
            )[0]
            
            return translated_text
            
        except Exception as e:
            if self.config.get("verbose", False):
                print(f"❌ Translation error: {e}")
            return "[Translation Error]"
    
    def display_result(self, original, translated, language=None):
        """Display transcription and translation"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Prepare output
        lines = []
        
        if self.config.get("show_timestamp", True):
            lines.append(f"[{timestamp}]")
        
        # Original text
        lang_label = f" ({language})" if self.config.get("show_language", True) and language else ""
        original_line = f"🗣️  Original{lang_label}: {original}"
        
        # Truncate if needed
        max_len = self.config.get("max_display_length", 0)
        if max_len > 0:
            if len(original_line) > max_len:
                original_line = original_line[:max_len] + "..."
        
        lines.append(original_line)
        
        # Translated text
        translated_line = f"💬 Translated: {translated}"
        if max_len > 0 and len(translated_line) > max_len:
            translated_line = translated_line[:max_len] + "..."
        
        lines.append(translated_line)
        lines.append("-" * 80)
        
        # Print to console
        for line in lines:
            print(line)
        
        # Save to file if enabled
        if self.file_handle:
            for line in lines:
                self.file_handle.write(line + "\n")
            self.file_handle.flush()
    
    def process_audio_stream(self):
        """Main processing loop"""
        print("\n🎙️  Listening... (Press Ctrl+C to stop)\n")
        self.start_time = time.time()
        
        while self.is_running:
            try:
                # Get audio from queue
                audio_data = self.audio_queue.get(timeout=0.1)
                
                # Add to buffer
                self.audio_buffer.extend(audio_data)
                self.total_audio_processed += len(audio_data) / self.sample_rate
                
                # Process when buffer is full
                if len(self.audio_buffer) >= self.chunk_samples:
                    # Get chunk
                    audio_chunk = np.array(list(self.audio_buffer)[:self.chunk_samples])
                    
                    # Process
                    original, translated, language = self.process_audio_chunk(audio_chunk)
                    
                    if original and translated:
                        self.display_result(original, translated, language)
                    
                    # Remove processed samples, keep overlap
                    for _ in range(self.chunk_samples - self.buffer_samples):
                        if len(self.audio_buffer) > 0:
                            self.audio_buffer.popleft()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.error_count += 1
                if self.config.get("verbose", False):
                    print(f"❌ Processing error: {e}")
                continue
    
    def start(self):
        """Start the real-time translator"""
        self.is_running = True
        
        # Start processing thread
        processing_thread = threading.Thread(target=self.process_audio_stream, daemon=True)
        processing_thread.start()
        
        try:
            # Configure audio device
            device = self.config.get("audio_device", -1)
            if device == -1:
                device = None
            
            # Start audio stream
            with sd.InputStream(
                device=device,
                samplerate=self.sample_rate,
                channels=1,
                callback=self.audio_callback,
                blocksize=int(self.sample_rate * 0.1),
                dtype=np.float32
            ):
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
        
        # Close file handle
        if self.file_handle:
            self.file_handle.close()
        
        # Display statistics
        if self.start_time:
            duration = time.time() - self.start_time
            print("\n" + "=" * 80)
            print("📊 Session Statistics:")
            print(f"   Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
            print(f"   Audio Processed: {self.total_audio_processed:.1f} seconds")
            print(f"   Transcriptions: {self.transcription_count}")
            print(f"   Translations: {self.translation_count}")
            print(f"   Errors: {self.error_count}")
            
            if self.transcription_count > 0:
                avg_time = duration / self.transcription_count
                print(f"   Average Time per Transcription: {avg_time:.2f}s")
            
            if self.save_to_file:
                print(f"   Output saved to: {self.output_file}")
            
            print("=" * 80)
        
        print("\n👋 Goodbye!")


def list_audio_devices():
    """List available audio input devices"""
    print("\n📱 Available Audio Input Devices:\n")
    devices = sd.query_devices()
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"   [{i}] {device['name']}")
            print(f"       Channels: {device['max_input_channels']}, Sample Rate: {device['default_samplerate']} Hz")
    
    print()


def main():
    """Main entry point with command line arguments"""
    parser = argparse.ArgumentParser(
        description="Real-time Speech Translator - Whisper + NLLB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default config
  %(prog)s --config custom.ini                # Use custom config file
  %(prog)s --source ja --target eng_Latn      # Japanese to English
  %(prog)s --model small --save               # Use small model and save to file
  %(prog)s --list-devices                     # List available audio devices
        """
    )
    
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--source", "-s", help="Source language code (e.g., ko, ja, zh)")
    parser.add_argument("--target", "-t", help="Target language code (e.g., eng_Latn)")
    parser.add_argument("--model", "-m", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--save", action="store_true", help="Save transcriptions to file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--device", "-d", type=int, help="Audio device ID")
    parser.add_argument("--list-devices", action="store_true", help="List available audio devices")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU usage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # List devices and exit
    if args.list_devices:
        list_audio_devices()
        return
    
    # Print header
    print("=" * 80)
    print("  Real-time Speech Translator - Whisper + NLLB (Enhanced)")
    print("  Free & Offline Solution")
    print("=" * 80)
    print()
    
    # Prepare kwargs
    kwargs = {}
    if args.source:
        kwargs["source_language"] = args.source
    if args.target:
        kwargs["target_language"] = args.target
    if args.model:
        kwargs["whisper_model"] = args.model
    if args.save:
        kwargs["save_to_file"] = True
    if args.output:
        kwargs["output_file"] = args.output
    if args.device is not None:
        kwargs["audio_device"] = args.device
    if args.no_gpu:
        kwargs["use_gpu"] = False
    if args.verbose:
        kwargs["verbose"] = True
    
    # Create and start translator
    translator = EnhancedRealtimeTranslator(config_file=args.config, **kwargs)
    translator.start()


if __name__ == "__main__":
    main()

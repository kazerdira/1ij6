#!/usr/bin/env python3
"""
Batch Audio File Processor
Process multiple audio files and export transcriptions/translations
"""

import argparse
import os
import sys
from pathlib import Path
import soundfile as sf
import numpy as np
from typing import List, Dict
import json
from datetime import datetime
import logging
from tqdm import tqdm

from vad_translator import VADRealtimeTranslator
from export_utils import ExportManager


class BatchProcessor:
    """Process multiple audio files in batch"""
    
    def __init__(
        self,
        source_language="ko",
        target_language="eng_Latn",
        whisper_model="base",
        output_dir="outputs",
        export_format="all",
        use_vad=True
    ):
        """
        Initialize batch processor
        
        Args:
            source_language: Source language code
            target_language: Target language code
            whisper_model: Whisper model size
            output_dir: Output directory
            export_format: Export format (txt, json, srt, vtt, all)
            use_vad: Enable VAD
        """
        self.source_language = source_language
        self.target_language = target_language
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize translator
        self.logger.info("Initializing translator...")
        self.translator = VADRealtimeTranslator(
            source_language=source_language,
            target_language=target_language,
            whisper_model=whisper_model,
            vad_aggressiveness=3 if use_vad else 0,
            verbose=False
        )
        
        # Initialize exporter
        self.exporter = ExportManager()
        self.export_format = export_format
        
        # Statistics
        self.processed_files = 0
        self.failed_files = 0
        self.total_duration = 0
    
    def process_file(self, audio_path: Path) -> Dict:
        """
        Process a single audio file
        
        Args:
            audio_path: Path to audio file
        
        Returns:
            Dictionary with results
        """
        try:
            self.logger.info(f"Processing: {audio_path.name}")
            
            # Load audio
            audio_data, sample_rate = sf.read(str(audio_path))
            
            # Convert to mono if needed
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]
            
            # Resample if needed
            if sample_rate != 16000:
                from scipy import signal
                num_samples = int(len(audio_data) * 16000 / sample_rate)
                audio_data = signal.resample(audio_data, num_samples)
                sample_rate = 16000
            
            duration = len(audio_data) / sample_rate
            self.total_duration += duration
            
            # Process in chunks
            chunk_duration = 30  # 30 seconds per chunk
            chunk_samples = int(sample_rate * chunk_duration)
            
            transcriptions = []
            
            for i in range(0, len(audio_data), chunk_samples):
                chunk = audio_data[i:i + chunk_samples]
                start_time = i / sample_rate
                end_time = (i + len(chunk)) / sample_rate
                
                original, translated = self.translator.process_audio_chunk(chunk)
                
                if original and translated:
                    transcriptions.append({
                        "start": start_time,
                        "end": end_time,
                        "original": original,
                        "translated": translated
                    })
            
            if not transcriptions:
                self.logger.warning(f"No speech detected in {audio_path.name}")
                return {
                    "success": False,
                    "error": "No speech detected",
                    "file": str(audio_path)
                }
            
            # Export results
            self._export_results(audio_path, transcriptions)
            
            self.processed_files += 1
            
            return {
                "success": True,
                "file": str(audio_path),
                "duration": duration,
                "segments": len(transcriptions)
            }
        
        except Exception as e:
            self.logger.error(f"Error processing {audio_path.name}: {e}")
            self.failed_files += 1
            return {
                "success": False,
                "file": str(audio_path),
                "error": str(e)
            }
    
    def _export_results(self, audio_path: Path, transcriptions: List[Dict]):
        """Export transcriptions to various formats"""
        base_name = audio_path.stem
        
        if self.export_format in ["txt", "all"]:
            # Plain text export
            txt_path = self.output_dir / f"{base_name}.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"File: {audio_path.name}\n")
                f.write(f"Source: {self.source_language}\n")
                f.write(f"Target: {self.target_language}\n")
                f.write(f"Processed: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                
                for seg in transcriptions:
                    f.write(f"[{seg['start']:.2f}s - {seg['end']:.2f}s]\n")
                    f.write(f"Original: {seg['original']}\n")
                    f.write(f"Translated: {seg['translated']}\n\n")
        
        if self.export_format in ["json", "all"]:
            # JSON export
            json_path = self.output_dir / f"{base_name}.json"
            data = {
                "file": str(audio_path),
                "source_language": self.source_language,
                "target_language": self.target_language,
                "timestamp": datetime.now().isoformat(),
                "transcriptions": transcriptions
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        if self.export_format in ["srt", "all"]:
            # SRT subtitle export
            srt_path = self.output_dir / f"{base_name}.srt"
            self.exporter.export_srt(transcriptions, str(srt_path))
        
        if self.export_format in ["vtt", "all"]:
            # WebVTT subtitle export
            vtt_path = self.output_dir / f"{base_name}.vtt"
            self.exporter.export_vtt(transcriptions, str(vtt_path))
    
    def process_directory(self, input_dir: Path, recursive: bool = False) -> List[Dict]:
        """
        Process all audio files in a directory
        
        Args:
            input_dir: Input directory path
            recursive: Search subdirectories
        
        Returns:
            List of results for each file
        """
        # Supported audio formats
        audio_extensions = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.opus'}
        
        # Find audio files
        if recursive:
            audio_files = []
            for ext in audio_extensions:
                audio_files.extend(input_dir.rglob(f"*{ext}"))
        else:
            audio_files = []
            for ext in audio_extensions:
                audio_files.extend(input_dir.glob(f"*{ext}"))
        
        if not audio_files:
            self.logger.error(f"No audio files found in {input_dir}")
            return []
        
        self.logger.info(f"Found {len(audio_files)} audio files")
        
        # Process files with progress bar
        results = []
        for audio_file in tqdm(audio_files, desc="Processing"):
            result = self.process_file(audio_file)
            results.append(result)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print processing summary"""
        print("\n" + "=" * 80)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total Files: {len(results)}")
        print(f"Successful: {self.processed_files}")
        print(f"Failed: {self.failed_files}")
        print(f"Total Audio Duration: {self.total_duration:.1f} seconds ({self.total_duration/60:.1f} minutes)")
        
        if self.processed_files > 0:
            avg_time = self.total_duration / self.processed_files
            print(f"Average Duration per File: {avg_time:.1f} seconds")
        
        print(f"\nOutput Directory: {self.output_dir}")
        print("=" * 80)
        
        # Show failed files
        if self.failed_files > 0:
            print("\nFailed Files:")
            for result in results:
                if not result.get('success', False):
                    print(f"  - {result['file']}: {result.get('error', 'Unknown error')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Batch Audio File Processor for Speech Translation"
    )
    parser.add_argument("input", help="Input directory or file")
    parser.add_argument("--output", "-o", default="outputs", help="Output directory")
    parser.add_argument("--source", "-s", default="ko", help="Source language")
    parser.add_argument("--target", "-t", default="eng_Latn", help="Target language")
    parser.add_argument("--model", "-m", default="base", help="Whisper model size")
    parser.add_argument("--format", "-f", 
                       choices=["txt", "json", "srt", "vtt", "all"],
                       default="all",
                       help="Export format")
    parser.add_argument("--recursive", "-r", action="store_true",
                       help="Process subdirectories recursively")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD")
    parser.add_argument("--watch", action="store_true",
                       help="Watch directory for new files")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)
    
    print("=" * 80)
    print("  Batch Audio Processor - Real-time Speech Translator")
    print("=" * 80)
    print()
    
    # Initialize processor
    processor = BatchProcessor(
        source_language=args.source,
        target_language=args.target,
        whisper_model=args.model,
        output_dir=args.output,
        export_format=args.format,
        use_vad=not args.no_vad
    )
    
    # Process files
    if input_path.is_file():
        # Single file
        result = processor.process_file(input_path)
        results = [result]
    else:
        # Directory
        results = processor.process_directory(input_path, args.recursive)
    
    # Print summary
    processor.print_summary(results)
    
    # Watch mode
    if args.watch:
        print("\n👁️  Watching directory for new files... (Press Ctrl+C to stop)")
        import time
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class AudioFileHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    path = Path(event.src_path)
                    if path.suffix.lower() in {'.wav', '.mp3', '.flac', '.m4a'}:
                        print(f"\n📁 New file detected: {path.name}")
                        processor.process_file(path)
        
        observer = Observer()
        observer.schedule(AudioFileHandler(), str(input_path), recursive=args.recursive)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


if __name__ == "__main__":
    main()

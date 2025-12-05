#!/usr/bin/env python3
"""
GUI Application for Real-time Speech Translator
Simple Tkinter interface for easy use
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import queue
import sounddevice as sd
import numpy as np
from datetime import datetime
import sys

try:
    from vad_translator import VADRealtimeTranslator
    from export_utils import ExportManager
except ImportError:
    print("Error: Required modules not found. Make sure all files are in the same directory.")
    sys.exit(1)


class TranslatorGUI:
    """GUI Application for Real-time Translator"""
    
    def __init__(self, root):
        """Initialize GUI"""
        self.root = root
        self.root.title("Real-time Speech Translator")
        self.root.geometry("800x600")
        
        # Variables
        self.translator = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        
        # Setup UI
        self._create_widgets()
        self._setup_styles()
        
        # Statistics
        self.transcription_count = 0
        self.start_time = None
    
    def _setup_styles(self):
        """Setup ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
    
    def _create_widgets(self):
        """Create GUI widgets"""
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Source Language
        ttk.Label(config_frame, text="Source Language:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_lang_var = tk.StringVar(value="ko")
        source_lang_combo = ttk.Combobox(
            config_frame,
            textvariable=self.source_lang_var,
            values=["ko", "ja", "zh", "en", "es", "fr", "de", "ru", "ar"],
            width=10
        )
        source_lang_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Target Language
        ttk.Label(config_frame, text="Target Language:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.target_lang_var = tk.StringVar(value="eng_Latn")
        target_lang_combo = ttk.Combobox(
            config_frame,
            textvariable=self.target_lang_var,
            values=["eng_Latn", "fra_Latn", "spa_Latn", "deu_Latn", "kor_Hang", "jpn_Jpan"],
            width=12
        )
        target_lang_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Model Size
        ttk.Label(config_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value="base")
        model_combo = ttk.Combobox(
            config_frame,
            textvariable=self.model_var,
            values=["tiny", "base", "small", "medium"],
            width=10
        )
        model_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # VAD Option
        self.vad_var = tk.BooleanVar(value=True)
        vad_check = ttk.Checkbutton(config_frame, text="Enable VAD", variable=self.vad_var)
        vad_check.grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        
        # Control Frame
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Start/Stop Button
        self.start_button = ttk.Button(
            control_frame,
            text="▶ Start Listening",
            command=self.toggle_listening,
            width=20
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        clear_button = ttk.Button(
            control_frame,
            text="Clear Output",
            command=self.clear_output,
            width=15
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Export Button
        export_button = ttk.Button(
            control_frame,
            text="Export Results",
            command=self.export_results,
            width=15
        )
        export_button.pack(side=tk.LEFT, padx=5)
        
        # Status Label
        self.status_label = ttk.Label(control_frame, text="Status: Ready", foreground="green")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Output Frame
        output_frame = ttk.LabelFrame(self.root, text="Transcriptions", padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Output Text
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            width=80,
            height=20,
            font=("Consolas", 10)
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags
        self.output_text.tag_config("timestamp", foreground="gray")
        self.output_text.tag_config("original", foreground="blue")
        self.output_text.tag_config("translated", foreground="green", font=("Consolas", 10, "bold"))
        
        # Statistics Frame
        stats_frame = ttk.Frame(self.root, padding=5)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.stats_label = ttk.Label(
            stats_frame,
            text="Transcriptions: 0 | Duration: 0s",
            font=("Arial", 9)
        )
        self.stats_label.pack(side=tk.LEFT)
        
        # Store transcriptions for export
        self.transcriptions = []
    
    def toggle_listening(self):
        """Start or stop listening"""
        if not self.is_running:
            self.start_listening()
        else:
            self.stop_listening()
    
    def start_listening(self):
        """Start listening to microphone"""
        try:
            # Update status
            self.status_label.config(text="Status: Initializing...", foreground="orange")
            self.start_button.config(state=tk.DISABLED)
            self.root.update()
            
            # Initialize translator
            self.translator = VADRealtimeTranslator(
                source_language=self.source_lang_var.get(),
                target_language=self.target_lang_var.get(),
                whisper_model=self.model_var.get(),
                vad_aggressiveness=3 if self.vad_var.get() else 0,
                verbose=False
            )
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._process_audio, daemon=True)
            self.processing_thread.start()
            
            # Update UI
            self.status_label.config(text="Status: Listening...", foreground="green")
            self.start_button.config(text="⏹ Stop Listening", state=tk.NORMAL)
            
            self.append_output("🎙️ Started listening...\n\n", "timestamp")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start translator:\n{e}")
            self.status_label.config(text="Status: Error", foreground="red")
            self.start_button.config(state=tk.NORMAL)
    
    def stop_listening(self):
        """Stop listening"""
        self.is_running = False
        
        if self.translator:
            self.translator.stop()
        
        # Update UI
        self.status_label.config(text="Status: Stopped", foreground="gray")
        self.start_button.config(text="▶ Start Listening", state=tk.NORMAL)
        
        # Show statistics
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.stats_label.config(
                text=f"Transcriptions: {self.transcription_count} | Duration: {duration:.0f}s"
            )
        
        self.append_output("\n🛑 Stopped listening.\n", "timestamp")
    
    def _process_audio(self):
        """Process audio in background thread"""
        try:
            with sd.InputStream(
                samplerate=16000,
                channels=1,
                callback=lambda indata, frames, time, status: self.audio_queue.put(indata[:, 0]),
                blocksize=1600,
                dtype=np.float32
            ):
                audio_buffer = []
                chunk_samples = 48000  # 3 seconds
                
                while self.is_running:
                    try:
                        audio_data = self.audio_queue.get(timeout=0.1)
                        audio_buffer.extend(audio_data)
                        
                        if len(audio_buffer) >= chunk_samples:
                            audio_chunk = np.array(audio_buffer[:chunk_samples])
                            
                            # Process
                            original, translated = self.translator.process_audio_chunk(audio_chunk)
                            
                            if original and translated:
                                self._display_result(original, translated)
                            
                            # Keep overlap
                            audio_buffer = audio_buffer[chunk_samples - 16000:]
                    
                    except queue.Empty:
                        continue
                    except Exception as e:
                        print(f"Processing error: {e}")
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Audio error:\n{e}"))
            self.root.after(0, self.stop_listening)
    
    def _display_result(self, original, translated):
        """Display transcription result"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Append to output
        self.append_output(f"[{timestamp}]\n", "timestamp")
        self.append_output(f"🗣️ {original}\n", "original")
        self.append_output(f"💬 {translated}\n\n", "translated")
        self.append_output("-" * 80 + "\n", "timestamp")
        
        # Store for export
        self.transcriptions.append({
            "timestamp": timestamp,
            "original": original,
            "translated": translated
        })
        
        self.transcription_count += 1
        
        # Update stats
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.stats_label.config(
                text=f"Transcriptions: {self.transcription_count} | Duration: {duration:.0f}s"
            )
    
    def append_output(self, text, tag=None):
        """Append text to output"""
        self.output_text.insert(tk.END, text, tag)
        self.output_text.see(tk.END)
    
    def clear_output(self):
        """Clear output text"""
        if messagebox.askyesno("Clear Output", "Clear all transcriptions?"):
            self.output_text.delete(1.0, tk.END)
            self.transcriptions = []
            self.transcription_count = 0
            self.stats_label.config(text="Transcriptions: 0 | Duration: 0s")
    
    def export_results(self):
        """Export transcriptions to file"""
        if not self.transcriptions:
            messagebox.showinfo("Export", "No transcriptions to export!")
            return
        
        # Ask for file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("SRT subtitles", "*.srt"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            # Determine format from extension
            ext = file_path.split('.')[-1].lower()
            
            if ext == "txt":
                # Export as text
                with open(file_path, 'w', encoding='utf-8') as f:
                    for trans in self.transcriptions:
                        f.write(f"[{trans['timestamp']}]\n")
                        f.write(f"Original: {trans['original']}\n")
                        f.write(f"Translated: {trans['translated']}\n\n")
            
            elif ext == "json":
                # Export as JSON
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "transcriptions": self.transcriptions,
                        "source_language": self.source_lang_var.get(),
                        "target_language": self.target_lang_var.get(),
                        "total": len(self.transcriptions)
                    }, f, indent=2, ensure_ascii=False)
            
            elif ext == "srt":
                # Export as SRT
                exporter = ExportManager()
                # Convert to format expected by exporter
                srt_data = []
                for i, trans in enumerate(self.transcriptions):
                    srt_data.append({
                        "start": i * 3,  # Approximate timing
                        "end": (i + 1) * 3,
                        "original": trans['original'],
                        "translated": trans['translated']
                    })
                exporter.export_srt(srt_data, file_path)
            
            messagebox.showinfo("Export", f"Exported successfully to:\n{file_path}")
        
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = TranslatorGUI(root)
    
    # Handle window close
    def on_closing():
        if app.is_running:
            if messagebox.askokcancel("Quit", "Stop listening and quit?"):
                app.stop_listening()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Run
    root.mainloop()


if __name__ == "__main__":
    main()

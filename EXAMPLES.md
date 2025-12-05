# Real-time Speech Translator - Usage Examples

This document provides practical examples and code snippets for various use cases.

---

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Command Line Examples](#command-line-examples)
3. [Configuration Examples](#configuration-examples)
4. [Integration Examples](#integration-examples)
5. [Advanced Use Cases](#advanced-use-cases)

---

## Basic Usage

### Example 1: Korean to English (Default)

```bash
# Simple run with defaults
python realtime_translator.py
```

### Example 2: Japanese to English

```bash
python realtime_translator_enhanced.py --source ja --target eng_Latn
```

### Example 3: Chinese to Spanish

```bash
python realtime_translator_enhanced.py --source zh --target spa_Latn --model small
```

---

## Command Line Examples

### Using Different Models

```bash
# Fastest (tiny model)
python realtime_translator_enhanced.py --model tiny

# Balanced (base model - default)
python realtime_translator_enhanced.py --model base

# Better accuracy (small model)
python realtime_translator_enhanced.py --model small

# Best quality (medium model - requires more RAM)
python realtime_translator_enhanced.py --model medium
```

### Saving Transcriptions

```bash
# Save to default file (transcriptions.txt)
python realtime_translator_enhanced.py --save

# Save to custom file
python realtime_translator_enhanced.py --save --output my_translations.txt
```

### Using Specific Audio Device

```bash
# List available devices
python realtime_translator_enhanced.py --list-devices

# Use device ID 2
python realtime_translator_enhanced.py --device 2
```

### Disable GPU

```bash
# Force CPU usage
python realtime_translator_enhanced.py --no-gpu
```

### Verbose Mode

```bash
# Show detailed logs
python realtime_translator_enhanced.py --verbose
```

---

## Configuration Examples

### Config 1: Meeting Transcription (Korean → English)

```ini
# config_meeting.ini
[General]
verbose = true
save_to_file = true
output_file = meeting_transcript.txt

[Audio]
sample_rate = 16000
chunk_duration = 4
buffer_duration = 1.5

[Whisper]
model_size = small
source_language = ko

[Translation]
target_language = eng_Latn
num_beams = 5
```

Run with:
```bash
python realtime_translator_enhanced.py --config config_meeting.ini
```

### Config 2: Fast Real-time (Japanese → English)

```ini
# config_fast.ini
[General]
verbose = false
save_to_file = false

[Audio]
sample_rate = 16000
chunk_duration = 2
buffer_duration = 0.5

[Whisper]
model_size = tiny
source_language = ja

[Translation]
target_language = eng_Latn
num_beams = 3

[Performance]
use_gpu = true
fp16 = true
```

### Config 3: High Quality (Chinese → English)

```ini
# config_quality.ini
[Audio]
chunk_duration = 5
buffer_duration = 2

[Whisper]
model_size = medium
source_language = zh

[Translation]
target_language = eng_Latn
num_beams = 7
```

---

## Integration Examples

### Example 1: Process Audio File

```python
#!/usr/bin/env python3
"""Process an audio file instead of real-time input"""

import soundfile as sf
from realtime_translator import RealtimeTranslator

# Load audio file
audio_data, sample_rate = sf.read("meeting_recording.wav")

# Create translator
translator = RealtimeTranslator(
    source_language="ko",
    target_language="eng_Latn",
    whisper_model="base"
)

# Process audio
print("Processing audio file...")
original, translated = translator.process_audio_chunk(audio_data)

print(f"\nOriginal: {original}")
print(f"Translated: {translated}")
```

### Example 2: Flask Web API

```python
#!/usr/bin/env python3
"""Flask API for real-time translation"""

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from realtime_translator import RealtimeTranslator
import numpy as np
import base64

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize translator
translator = RealtimeTranslator(
    source_language="ko",
    target_language="eng_Latn",
    whisper_model="base"
)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('audio_chunk')
def handle_audio(data):
    """Handle incoming audio chunks from web client"""
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(data['audio'])
        audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
        
        # Process
        original, translated = translator.process_audio_chunk(audio_array)
        
        if original and translated:
            emit('transcription', {
                'original': original,
                'translated': translated,
                'timestamp': data.get('timestamp')
            })
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
```

### Example 3: Save to Database

```python
#!/usr/bin/env python3
"""Save transcriptions to SQLite database"""

import sqlite3
from datetime import datetime
from realtime_translator_enhanced import EnhancedRealtimeTranslator

class DatabaseTranslator(EnhancedRealtimeTranslator):
    """Extended translator that saves to database"""
    
    def __init__(self, db_path='transcriptions.db', **kwargs):
        super().__init__(**kwargs)
        
        # Setup database
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                original_text TEXT,
                translated_text TEXT,
                source_language TEXT,
                target_language TEXT
            )
        ''')
        self.conn.commit()
    
    def display_result(self, original, translated, language=None):
        """Override to save to database"""
        # Call parent method for console display
        super().display_result(original, translated, language)
        
        # Save to database
        timestamp = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO transcriptions 
            (timestamp, original_text, translated_text, source_language, target_language)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, original, translated, language, self.config['target_language']))
        self.conn.commit()
    
    def stop(self):
        """Close database connection"""
        super().stop()
        self.conn.close()
        print(f"Database saved to: {self.db_path}")

if __name__ == '__main__':
    translator = DatabaseTranslator(
        source_language="ko",
        target_language="eng_Latn"
    )
    translator.start()
```

### Example 4: WebSocket Server

```python
#!/usr/bin/env python3
"""WebSocket server for real-time translation"""

import asyncio
import websockets
import json
import numpy as np
from realtime_translator import RealtimeTranslator

# Initialize translator
translator = RealtimeTranslator(
    source_language="ko",
    target_language="eng_Latn",
    whisper_model="base"
)

async def handle_client(websocket, path):
    """Handle WebSocket client connection"""
    print(f"Client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            # Expect JSON with audio data
            data = json.loads(message)
            
            # Convert audio data
            audio_array = np.array(data['audio'], dtype=np.float32)
            
            # Process
            original, translated = translator.process_audio_chunk(audio_array)
            
            if original and translated:
                # Send result back
                result = {
                    'original': original,
                    'translated': translated,
                    'timestamp': data.get('timestamp')
                }
                await websocket.send(json.dumps(result))
    
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")

async def main():
    """Start WebSocket server"""
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("WebSocket server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Advanced Use Cases

### Use Case 1: Subtitle Generator for Video

```python
#!/usr/bin/env python3
"""Generate subtitles from video file"""

import subprocess
import tempfile
import os
from realtime_translator import RealtimeTranslator
import soundfile as sf

def extract_audio(video_path, output_path):
    """Extract audio from video using ffmpeg"""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def generate_srt(transcriptions, output_path):
    """Generate SRT subtitle file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, (start, end, original, translated) in enumerate(transcriptions, 1):
            # Format timestamps
            start_time = format_timestamp(start)
            end_time = format_timestamp(end)
            
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{original}\n")
            f.write(f"{translated}\n\n")

def format_timestamp(seconds):
    """Convert seconds to SRT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def main(video_path):
    """Main subtitle generation function"""
    print(f"Processing video: {video_path}")
    
    # Extract audio
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_path = tmp.name
    
    print("Extracting audio...")
    extract_audio(video_path, audio_path)
    
    # Load audio
    print("Loading audio...")
    audio_data, sample_rate = sf.read(audio_path)
    
    # Initialize translator
    print("Initializing translator...")
    translator = RealtimeTranslator(
        source_language="ko",
        target_language="eng_Latn",
        whisper_model="small"
    )
    
    # Process audio in chunks
    print("Processing audio...")
    chunk_duration = 10  # 10 seconds per chunk
    chunk_samples = sample_rate * chunk_duration
    transcriptions = []
    
    for i in range(0, len(audio_data), chunk_samples):
        chunk = audio_data[i:i + chunk_samples]
        start_time = i / sample_rate
        end_time = (i + len(chunk)) / sample_rate
        
        original, translated = translator.process_audio_chunk(chunk)
        
        if original and translated:
            transcriptions.append((start_time, end_time, original, translated))
            print(f"  [{start_time:.1f}s - {end_time:.1f}s] Processed")
    
    # Generate SRT file
    output_srt = os.path.splitext(video_path)[0] + '.srt'
    print(f"Generating subtitles: {output_srt}")
    generate_srt(transcriptions, output_srt)
    
    # Cleanup
    os.unlink(audio_path)
    
    print("Done!")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python subtitle_generator.py <video_file>")
        sys.exit(1)
    
    main(sys.argv[1])
```

### Use Case 2: Multi-language Conference Call

```python
#!/usr/bin/env python3
"""Translate multiple audio streams simultaneously"""

import threading
from realtime_translator import RealtimeTranslator

class MultiLanguageTranslator:
    """Handle multiple translation streams"""
    
    def __init__(self):
        self.translators = {}
        self.threads = []
    
    def add_stream(self, stream_id, source_lang, target_lang):
        """Add a translation stream"""
        translator = RealtimeTranslator(
            source_language=source_lang,
            target_language=target_lang,
            whisper_model="base"
        )
        self.translators[stream_id] = translator
        
        # Start in separate thread
        thread = threading.Thread(
            target=translator.start,
            daemon=True
        )
        self.threads.append(thread)
        thread.start()
        
        print(f"Started stream {stream_id}: {source_lang} → {target_lang}")
    
    def stop_all(self):
        """Stop all translation streams"""
        for translator in self.translators.values():
            translator.stop()

# Example usage
if __name__ == '__main__':
    conference = MultiLanguageTranslator()
    
    # Stream 1: Korean speaker
    conference.add_stream('korean_speaker', 'ko', 'eng_Latn')
    
    # Stream 2: Japanese speaker
    conference.add_stream('japanese_speaker', 'ja', 'eng_Latn')
    
    # Stream 3: Chinese speaker
    conference.add_stream('chinese_speaker', 'zh', 'eng_Latn')
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all streams...")
        conference.stop_all()
```

### Use Case 3: Live Streaming Caption Generator

```python
#!/usr/bin/env python3
"""Generate live captions for streaming"""

import time
from collections import deque
from realtime_translator_enhanced import EnhancedRealtimeTranslator

class CaptionGenerator(EnhancedRealtimeTranslator):
    """Extended translator with caption overlay"""
    
    def __init__(self, caption_duration=5, **kwargs):
        super().__init__(**kwargs)
        self.caption_duration = caption_duration
        self.captions = deque(maxlen=3)  # Keep last 3 captions
    
    def display_result(self, original, translated, language=None):
        """Display as caption overlay"""
        # Add timestamp
        timestamp = time.time()
        caption = {
            'text': translated,
            'timestamp': timestamp,
            'expires': timestamp + self.caption_duration
        }
        self.captions.append(caption)
        
        # Clear screen
        print("\033[2J\033[H")
        
        # Display active captions
        print("=" * 80)
        print("LIVE CAPTIONS")
        print("=" * 80)
        print()
        
        current_time = time.time()
        for cap in self.captions:
            if cap['expires'] > current_time:
                print(f"  {cap['text']}")
        
        print()
        print("=" * 80)

if __name__ == '__main__':
    generator = CaptionGenerator(
        source_language="ko",
        target_language="eng_Latn",
        caption_duration=5
    )
    generator.start()
```

---

## Performance Optimization Tips

### For Low-latency (CPU):
- Use `tiny` model
- Set `chunk_duration=2`
- Set `buffer_duration=0.5`
- Disable verbose mode

### For Best Accuracy:
- Use `medium` or `large` model
- Set `chunk_duration=5`
- Set `buffer_duration=2`
- Use GPU if available
- Increase `num_beams` to 7-10

### For Batch Processing:
- Use larger models
- Process longer chunks
- Save to file/database for later review
- Use GPU acceleration

---

## Troubleshooting Common Issues

### Issue: Delayed transcriptions
**Solution:** Reduce `chunk_duration` to 2 seconds

### Issue: Inaccurate transcriptions
**Solution:** Use larger model (`small` or `medium`) and increase `chunk_duration`

### Issue: High CPU usage
**Solution:** Use `tiny` model or enable GPU

### Issue: Out of memory
**Solution:** Use smaller model or reduce `chunk_duration`

---

For more information, see the main README.md file.

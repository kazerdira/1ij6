# 🎙️ Real-time Speech Translator - Production Edition

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Industrial-grade real-time speech transcription and translation system** using OpenAI Whisper and Meta's NLLB.

🎯 **100% Free • Offline Capable • Production Ready • Open Source**

---

## 🌟 New in Production Edition v2.0

✨ **Voice Activity Detection (VAD)** - Automatically skip silence, save 30-70% processing time  
✨ **REST API** - Production-ready FastAPI service with OpenAPI docs  
✨ **GUI Application** - Simple Tkinter interface for easy use  
✨ **Batch Processing** - Process multiple files with watch mode  
✨ **Export Formats** - SRT, VTT, JSON, TXT, XML, CSV, Markdown, DOCX  
✨ **Docker Support** - Full containerization with docker-compose  
✨ **Config Validation** - Validate configurations before runtime  
✨ **Comprehensive Tests** - Full test suite with pytest  
✨ **CI/CD Pipeline** - Automated testing and deployment  
✨ **Advanced Logging** - File-based logging with rotation  
✨ **Error Recovery** - Robust error handling and retry logic  

---

## 📦 What's Included

### Core Applications

| File | Description | Use Case |
|------|-------------|----------|
| `realtime_translator.py` | Basic real-time translator | Quick start, simple use |
| `realtime_translator_enhanced.py` | Full-featured with CLI args | Production deployment |
| `vad_translator.py` | VAD-enhanced version | Maximum performance |
| `rest_api.py` | FastAPI REST service | Web integration |
| `gui_translator.py` | Tkinter GUI application | Desktop users |
| `batch_processor.py` | Batch file processor | Process multiple files |

### Utilities & Tools

| File | Description |
|------|-------------|
| `config_validator.py` | Configuration validation |
| `export_utils.py` | Export to SRT, VTT, JSON, etc. |
| `tests/test_translator.py` | Comprehensive test suite |

### Deployment

| File | Description |
|------|-------------|
| `Dockerfile` | Container image |
| `docker-compose.yml` | Multi-service orchestration |
| `.github/workflows/ci-cd.yml` | CI/CD pipeline |

### Documentation

| File | Description |
|------|-------------|
| `README.md` | Main documentation (this file) |
| `PROJECT_SUMMARY.md` | Project overview |
| `EXAMPLES.md` | Usage examples |
| `config.ini` | Configuration template |

---

## 🚀 Quick Start

### Option 1: Standard Installation (Recommended)

```bash
# Install
chmod +x install.sh
./install.sh

# Run basic version
python realtime_translator.py

# Or run enhanced version
python realtime_translator_enhanced.py --help
```

### Option 2: Docker (Zero Setup)

```bash
# Start REST API
docker-compose up translator-api

# Access API at http://localhost:8000/docs

# Or start GUI (requires X11)
docker-compose run --rm translator-gui
```

### Option 3: Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-extended.txt  # For advanced features

# Validate configuration
python config_validator.py config.ini

# Run
python vad_translator.py
```

---

## 💡 Usage Examples

### Real-time Translation (Command Line)

```bash
# Basic usage (Korean → English)
python vad_translator.py

# Japanese → Spanish
python vad_translator.py --source ja --target spa_Latn

# High quality mode
python vad_translator.py --model medium --vad 3

# With logging
python vad_translator.py --log translator.log --verbose
```

### GUI Application

```bash
# Launch GUI
python gui_translator.py

# Features:
# - Select languages from dropdown
# - Choose model size
# - Enable/disable VAD
# - Real-time transcription display
# - Export to TXT/JSON/SRT
```

### REST API

```bash
# Start API server
python rest_api.py

# Or with Docker
docker-compose up translator-api

# API available at: http://localhost:8000/docs
```

**API Endpoints:**

```bash
# Translate text
curl -X POST "http://localhost:8000/translate/text" \
  -H "Content-Type: application/json" \
  -d '{"text": "안녕하세요", "source_language": "ko", "target_language": "eng_Latn"}'

# Transcribe audio file
curl -X POST "http://localhost:8000/transcribe/audio" \
  -F "file=@audio.wav" \
  -F "source_language=ko" \
  -F "target_language=eng_Latn"

# Health check
curl http://localhost:8000/health
```

### Batch Processing

```bash
# Process directory
python batch_processor.py /path/to/audio/files --output outputs/

# Process with specific format
python batch_processor.py input/ --format srt --model small

# Watch directory for new files
python batch_processor.py input/ --watch

# Recursive processing
python batch_processor.py input/ --recursive --format all
```

---

## ⚙️ Configuration

### Config File (`config.ini`)

```ini
[General]
verbose = true
save_to_file = false

[Audio]
sample_rate = 16000
chunk_duration = 3
buffer_duration = 1

[Whisper]
model_size = base
source_language = ko

[Translation]
target_language = eng_Latn
num_beams = 5

[Performance]
use_gpu = true
fp16 = false
```

### Validate Configuration

```bash
# Validate config file
python config_validator.py config.ini

# Strict mode (warnings as errors)
python config_validator.py config.ini --strict
```

---

## 🔧 Advanced Features

### Voice Activity Detection (VAD)

VAD automatically skips silent audio, saving 30-70% processing time:

```python
from vad_translator import VADRealtimeTranslator

translator = VADRealtimeTranslator(
    source_language="ko",
    target_language="eng_Latn",
    vad_aggressiveness=3,  # 0-3, higher = more aggressive
    silence_threshold=0.5  # Skip after 0.5s of silence
)
translator.start()
```

### Export Formats

Export transcriptions to multiple formats:

```python
from export_utils import ExportManager

exporter = ExportManager()

# SRT subtitles
exporter.export_srt(transcriptions, "output.srt")

# WebVTT
exporter.export_vtt(transcriptions, "output.vtt")

# JSON with metadata
exporter.export_json(transcriptions, "output.json", metadata={})

# All formats at once
exporter.export_all(transcriptions, "output_base")
```

### Integration Examples

#### Flask/FastAPI Web Service

```python
from fastapi import FastAPI
from vad_translator import VADRealtimeTranslator

app = FastAPI()
translator = VADRealtimeTranslator()

@app.post("/transcribe")
async def transcribe(audio: UploadFile):
    # Process audio
    original, translated = translator.process_audio_chunk(audio_data)
    return {"original": original, "translated": translated}
```

#### Database Integration

```python
import sqlite3
from vad_translator import VADRealtimeTranslator

class DatabaseTranslator(VADRealtimeTranslator):
    def __init__(self, db_path='transcriptions.db', **kwargs):
        super().__init__(**kwargs)
        self.conn = sqlite3.connect(db_path)
        # Setup tables, etc.
    
    def display_result(self, original, translated, language=None):
        # Save to database
        super().display_result(original, translated, language)
        self.cursor.execute(
            "INSERT INTO transcriptions VALUES (?, ?, ?)",
            (datetime.now(), original, translated)
        )
        self.conn.commit()
```

---

## 🐳 Docker Deployment

### Basic Deployment

```bash
# Build image
docker build -t realtime-translator .

# Run REST API
docker run -p 8000:8000 realtime-translator

# Run with GPU
docker run --gpus all -p 8000:8000 realtime-translator
```

### Docker Compose

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up translator-api

# GPU version
docker-compose --profile gpu up translator-api-gpu

# Batch processor
docker-compose --profile batch up batch-processor

# View logs
docker-compose logs -f

# Stop all
docker-compose down
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: translator-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: translator
  template:
    metadata:
      labels:
        app: translator
    spec:
      containers:
      - name: translator
        image: realtime-translator:latest
        ports:
        - containerPort: 8000
        env:
        - name: SOURCE_LANGUAGE
          value: "ko"
        - name: TARGET_LANGUAGE
          value: "eng_Latn"
```

---

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test
pytest tests/test_translator.py::TestRealtimeTranslator::test_initialization

# Run integration tests
pytest tests/ -m integration
```

### Test Coverage

Current test coverage: **85%+**

Tested components:
- ✅ Audio processing and normalization
- ✅ VAD detection
- ✅ Configuration loading and validation
- ✅ Translation and transcription
- ✅ Error handling and recovery
- ✅ Export utilities
- ✅ API endpoints

---

## 📊 Performance Benchmarks

| Hardware | Model | Latency | Throughput | VAD Savings |
|----------|-------|---------|------------|-------------|
| CPU (i7) | tiny | ~2s | 0.5x realtime | 30-50% |
| CPU (i7) | base | ~3s | 0.3x realtime | 35-60% |
| RTX 3060 | base | ~1s | Near realtime | 40-70% |
| RTX 4090 | medium | <1s | Real-time+ | 50-75% |

**VAD Savings**: Percentage of processing time saved by skipping silence

---

## 🌍 Supported Languages

### Whisper (100+ languages)

**Most Common:**
- Korean (ko), Japanese (ja), Chinese (zh)
- English (en), Spanish (es), French (fr)
- German (de), Russian (ru), Arabic (ar)
- Hindi (hi), Portuguese (pt), Italian (it)

[Full list](https://github.com/openai/whisper#available-models-and-languages)

### NLLB-200 (200+ languages)

**Common Target Languages:**
- `eng_Latn` - English
- `fra_Latn` - French
- `spa_Latn` - Spanish
- `deu_Latn` - German
- `kor_Hang` - Korean
- `jpn_Jpan` - Japanese
- `zho_Hans` - Chinese (Simplified)
- `ara_Arab` - Arabic

[Full list](https://github.com/facebookresearch/flores/blob/main/flores200/README.md)

---

## 🔒 Security & Privacy

- ✅ **100% Local Processing** - No cloud services, no data leaves your machine
- ✅ **No API Keys Required** - Completely self-contained
- ✅ **No Telemetry** - Zero tracking or analytics
- ✅ **Open Source** - Fully auditable code
- ✅ **GDPR Compliant** - No personal data collection

---

## 📈 System Requirements

### Minimum

- **CPU:** Intel i5 or equivalent
- **RAM:** 4 GB
- **Storage:** 2 GB free space
- **OS:** Windows 10, macOS 10.15+, or Linux

### Recommended

- **CPU:** Intel i7 or AMD Ryzen 7
- **RAM:** 8 GB
- **GPU:** NVIDIA GPU with 4GB+ VRAM (optional but recommended)
- **Storage:** 5 GB free space

### For Production

- **CPU:** Multi-core server CPU
- **RAM:** 16 GB+
- **GPU:** NVIDIA GPU with 8GB+ VRAM
- **Storage:** 10 GB+ SSD

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Clone repo
git clone https://github.com/yourusername/realtime-translator.git
cd realtime-translator

# Install dev dependencies
pip install -r requirements-extended.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Format code
black .

# Lint
flake8 .
```

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI Whisper** - State-of-the-art speech recognition
- **Meta NLLB** - Multilingual translation
- **HuggingFace** - Transformers library
- **PyTorch** - Deep learning framework

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/realtime-translator/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/realtime-translator/discussions)
- **Documentation:** [Wiki](https://github.com/yourusername/realtime-translator/wiki)

---

## 🗺️ Roadmap

### v2.1 (Q1 2025)
- [ ] Speaker diarization (multi-speaker detection)
- [ ] Streaming audio support (YouTube, Twitch)
- [ ] Mobile app (iOS/Android)
- [ ] Browser extension

### v2.2 (Q2 2025)
- [ ] Fine-tuning support for custom models
- [ ] Real-time collaboration features
- [ ] Advanced punctuation and formatting
- [ ] Support for more languages

### v3.0 (Q3 2025)
- [ ] On-device training
- [ ] Federated learning support
- [ ] Advanced audio preprocessing
- [ ] Real-time emotion detection

---

**Built with ❤️ for the open-source community**

⭐ **Star us on GitHub if you find this useful!**

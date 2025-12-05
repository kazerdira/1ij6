FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY requirements-extended.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-extended.txt

# Copy application files
COPY realtime_translator.py .
COPY realtime_translator_enhanced.py .
COPY vad_translator.py .
COPY config_validator.py .
COPY rest_api.py .
COPY batch_processor.py .
COPY export_utils.py .
COPY config.ini .

# Create directories for models and outputs
RUN mkdir -p /root/.cache/whisper \
    /root/.cache/huggingface \
    /app/outputs \
    /app/logs

# Expose port for REST API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default command (can be overridden)
CMD ["python", "rest_api.py"]

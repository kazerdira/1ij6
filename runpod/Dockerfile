# RunPod Serverless - GPU Docker Image
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy handler
COPY handler.py .

# Pre-download Whisper model only (smaller, fits in build)
RUN python -c "import whisper; whisper.load_model('base')"

# NLLB model will be downloaded on first request (too large for build)
# This adds ~30s to first cold start but ensures reliable builds

# Set environment variables
ENV WHISPER_MODEL=base
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models

# Start handler
CMD ["python", "-u", "handler.py"]

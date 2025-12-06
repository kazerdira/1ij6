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

# Pre-download models (baked into image for fast cold starts)
RUN python -c "import whisper; whisper.load_model('base')"
RUN python -c "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; \
    AutoTokenizer.from_pretrained('facebook/nllb-200-distilled-600M'); \
    AutoModelForSeq2SeqLM.from_pretrained('facebook/nllb-200-distilled-600M')"

# Set environment variables
ENV WHISPER_MODEL=base
ENV PYTHONUNBUFFERED=1

# Start handler
CMD ["python", "-u", "handler.py"]

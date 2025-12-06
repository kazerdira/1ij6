# RunPod Serverless Deployment Guide

## 🚀 Quick Start

### Step 1: Create RunPod Account
1. Go to **https://runpod.io**
2. Sign up and add credits ($10-25 to start)

### Step 2: Build & Push Docker Image

**Option A: Use RunPod's Docker Registry (Easiest)**

```bash
# Login to Docker Hub (or use RunPod registry)
docker login

# Build the image
cd runpod
docker build -t YOUR_DOCKERHUB_USERNAME/translator-api:latest .

# Push to registry
docker push YOUR_DOCKERHUB_USERNAME/translator-api:latest
```

**Option B: Use GitHub Container Registry**
```bash
# Login to GitHub
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Build and push
docker build -t ghcr.io/kazerdira/translator-api:latest .
docker push ghcr.io/kazerdira/translator-api:latest
```

### Step 3: Create Serverless Endpoint

1. Go to **RunPod Console** → **Serverless**
2. Click **"+ New Endpoint"**
3. Configure:
   - **Name**: `translator-api`
   - **Docker Image**: `YOUR_DOCKERHUB_USERNAME/translator-api:latest`
   - **GPU**: Select `RTX 3090` or `RTX 4090` (cheapest with good performance)
   - **Min Workers**: `0` (scale to zero when idle)
   - **Max Workers**: `3` (scale up under load)
   - **Idle Timeout**: `5` seconds
   - **Execution Timeout**: `300` seconds

4. Click **"Create"**

### Step 4: Get Your API Endpoint

After creation, you'll get:
- **Endpoint ID**: `xxxxxxxxxxxxxxxx`
- **API URL**: `https://api.runpod.ai/v2/xxxxxxxxxxxxxxxx/runsync`

## 📡 API Usage

### Get your API Key
1. Go to **RunPod Console** → **Settings** → **API Keys**
2. Create a new key

### Translate Text
```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "action": "translate",
      "text": "Hello, how are you?",
      "source_language": "eng_Latn",
      "target_language": "fra_Latn"
    }
  }'
```

### Transcribe & Translate Audio
```bash
# First, convert audio to base64
AUDIO_BASE64=$(base64 -w 0 audio.wav)

curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"action\": \"transcribe\",
      \"audio_base64\": \"$AUDIO_BASE64\",
      \"source_language\": \"eng_Latn\",
      \"target_language\": \"fra_Latn\"
    }
  }"
```

### Health Check
```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {"action": "health"}}'
```

## 💰 Pricing

| GPU | Price/sec | Est. Monthly (1000 req) |
|-----|-----------|------------------------|
| RTX 3090 | $0.00031 | ~$5-10 |
| RTX 4090 | $0.00044 | ~$7-15 |
| A100 | $0.00076 | ~$12-25 |

**You only pay when processing requests!** Idle = $0

## 🌍 Supported Languages

NLLB-200 supports 200+ languages. Common codes:
- English: `eng_Latn`
- French: `fra_Latn`
- Spanish: `spa_Latn`
- German: `deu_Latn`
- Italian: `ita_Latn`
- Portuguese: `por_Latn`
- Chinese: `zho_Hans`
- Japanese: `jpn_Jpan`
- Korean: `kor_Hang`
- Arabic: `arb_Arab`
- Russian: `rus_Cyrl`

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small/medium/large) |

## 📊 Response Format

### Translation Response
```json
{
  "output": {
    "original": "Hello, how are you?",
    "translated": "Bonjour, comment allez-vous?",
    "source_language": "eng_Latn",
    "target_language": "fra_Latn",
    "duration_ms": 150.5
  },
  "status": "COMPLETED"
}
```

### Transcription Response
```json
{
  "output": {
    "transcribed": "Hello world",
    "translated": "Bonjour le monde",
    "source_language": "eng_Latn",
    "target_language": "fra_Latn",
    "duration_ms": 850.2
  },
  "status": "COMPLETED"
}
```

## ⚡ Performance Tips

1. **Use `base` Whisper model** - Best speed/accuracy tradeoff
2. **RTX 4090** - Best price/performance for this workload
3. **Keep Min Workers at 0** - Pay nothing when idle
4. **Batch requests** - If translating multiple texts, send them together

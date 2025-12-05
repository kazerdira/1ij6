# Production Translation API 🚀

This is a **production-ready** translation API with full security, reliability, and scalability features.

## Features ✨

### Security
- **API Key Authentication** - Generate and manage API keys per user
- **JWT Token Support** - Alternative authentication method
- **Rate Limiting** - Tier-based rate limits (free/basic/pro/enterprise)
- **Input Validation** - Prevents injection attacks and malformed data
- **Security Headers** - HTTPS, HSTS, CSP, XSS protection

### Reliability
- **Circuit Breaker** - Prevents cascading failures
- **Retry Logic** - Automatic retries with exponential backoff
- **Health Checks** - Comprehensive system monitoring

### Scalability
- **Async Processing** - Handle multiple requests concurrently
- **Redis Caching** - Cache translations to avoid redundant processing
- **Docker Support** - Easy deployment and scaling

## Quick Start 🏃

### Option 1: Docker (Recommended)

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Option 2: Manual Setup

1. **Install Redis** (required for rate limiting and caching):
```bash
# Windows: Use Docker
docker run -d -p 6379:6379 redis:alpine

# Linux/Mac
sudo apt install redis-server  # Ubuntu
brew install redis             # Mac
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the API**:
```bash
python api.py
```

4. **Open API docs**: http://localhost:8000/docs

## API Usage 📖

### 1. Health Check (No Auth Required)
```bash
curl http://localhost:8000/health
```

### 2. Create API Key (Admin Required)
First, you need an admin API key. For development, you can modify the code or use the default setup.

### 3. Translate Text
```bash
curl -X POST http://localhost:8000/translate/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "text": "안녕하세요",
    "source_language": "ko",
    "target_language": "eng_Latn"
  }'
```

### 4. Transcribe Audio
```bash
curl -X POST http://localhost:8000/transcribe/audio \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "file=@audio.wav" \
  -F "source_language=ko" \
  -F "target_language=eng_Latn"
```

## Rate Limits 📊

| Tier | Requests/Min | Requests/Day | Price |
|------|-------------|--------------|-------|
| Free | 10 | 1,000 | $0 |
| Basic | 50 | 10,000 | $29/month |
| Pro | 200 | 100,000 | $99/month |
| Enterprise | 1,000 | 1,000,000 | Custom |

## Project Structure 📁

```
production/
├── api.py                      # Main API application
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker build file
├── docker-compose.yml          # Docker Compose config
├── .env.example               # Environment variables template
│
├── security/                   # Security components
│   ├── __init__.py
│   ├── auth.py                # Authentication (API keys, JWT)
│   ├── rate_limiter.py        # Rate limiting with Redis
│   └── input_validator.py     # Input validation & sanitization
│
├── reliability/                # Reliability components
│   ├── __init__.py
│   ├── circuit_breaker.py     # Circuit breaker pattern
│   ├── retry_handler.py       # Retry with exponential backoff
│   └── health_checks.py       # Health monitoring
│
├── scalability/                # Scalability components
│   ├── __init__.py
│   ├── async_translator.py    # Async translator for concurrency
│   └── cache_manager.py       # Redis caching for translations
│
├── logs/                       # Log files
└── outputs/                    # Output files
```

## Environment Variables 🔧

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis hostname | localhost |
| `REDIS_PORT` | Redis port | 6379 |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | (auto-generated) |
| `SOURCE_LANGUAGE` | Default source language | ko |
| `TARGET_LANGUAGE` | Default target language | eng_Latn |
| `WHISPER_MODEL` | Whisper model size | base |
| `MAX_WORKERS` | Max concurrent workers | 4 |
| `ALLOWED_ORIGINS` | CORS allowed origins | * |

## Monitoring 📈

### Health Check Endpoints

- `/health` - Full health check (CPU, memory, GPU, models)
- `/health/simple` - Quick health check for load balancers
- `/metrics` - System metrics and statistics

### Logs

Logs are written to `logs/api_v2.log` and stdout.

## Scaling Tips 🚀

### For 10-100 Users
- Single API instance
- 4-8 workers
- Standard Redis

### For 100-1000 Users
- Multiple API instances behind load balancer
- 10-20 workers per instance
- Redis cluster

### For 1000+ Users
- Kubernetes deployment
- GPU instances for faster inference
- Message queue (RabbitMQ/SQS) for async processing
- CDN for static assets

## Troubleshooting 🔧

### Redis Connection Failed
```bash
# Check Redis is running
redis-cli ping

# Start Redis
docker run -d -p 6379:6379 redis:alpine
```

### Model Loading Slow
First load downloads models (~2GB). Subsequent starts use cached models.

### Rate Limit Exceeded
Check your tier limits or upgrade to a higher tier.

## Support 💬

For issues or questions, check the logs at `logs/api_v2.log`.

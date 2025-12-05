# 🚀 Quick Reference Card - Production Correctives

## ⚡ 60-Second Start

```bash
# 1. Install
pip install -r requirements-production.txt

# 2. Start Redis
docker run -d -p 6379:6379 redis:alpine

# 3. Copy correctives
cp -r security reliability scalability rest_api_v2.py ./

# 4. Run
python rest_api_v2.py

# 5. Test
curl http://localhost:8000/health
```

---

## 📦 What You Got

| Component | File | Purpose |
|-----------|------|---------|
| **Auth** | `security/auth.py` | API keys + JWT |
| **Rate Limit** | `security/rate_limiter.py` | Prevent abuse |
| **Validation** | `security/input_validator.py` | Sanitize inputs |
| **Circuit Breaker** | `reliability/circuit_breaker.py` | Fail fast |
| **Retry** | `reliability/retry_handler.py` | Auto-retry |
| **Health** | `reliability/health_checks.py` | Monitor system |
| **Async** | `scalability/async_translator.py` | Concurrent |
| **Cache** | `scalability/cache_manager.py` | Redis cache |
| **API v2** | `rest_api_v2.py` | Complete API |

---

## 🔑 Essential Code Snippets

### 1. Create API Key

```python
from security.auth import APIKeyManager

# Create key
api_key = APIKeyManager.generate_api_key(
    user_id="user_123",
    tier="pro"  # free, basic, pro, enterprise
)
print(f"Your API key: {api_key}")
```

### 2. Protect Endpoint

```python
from security.auth import AuthManager

@app.post("/endpoint")
async def my_endpoint(user: dict = Depends(AuthManager.verify_request)):
    # user contains: user_id, tier, requests_today
    tier = user.get("tier")  # free, basic, pro, enterprise
    return {"message": f"Hello {tier} user!"}
```

### 3. Add Rate Limiting

```python
from security.rate_limiter import rate_limit_middleware

@app.post("/endpoint")
@rate_limit_middleware(max_requests=60, window_seconds=60)
async def my_endpoint(request: Request):
    return {"message": "Rate limited!"}
```

### 4. Validate Input

```python
from security.input_validator import InputValidator

# Text
text = InputValidator.validate_text(user_input)

# File
audio_bytes = await InputValidator.validate_audio_file(uploaded_file)

# Path
safe_path = InputValidator.validate_file_path(user_path)
```

### 5. Add Circuit Breaker

```python
from reliability.circuit_breaker import circuit_breaker

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
def call_external_api():
    return requests.get("https://api.example.com")
```

### 6. Auto Retry

```python
from reliability.retry_handler import retry

@retry(max_attempts=3, base_delay=1.0)
def flaky_function():
    # Will retry up to 3 times with exponential backoff
    return do_something()
```

### 7. Health Checks

```python
from reliability.health_checks import health_monitor

# Check health
status = health_monitor.run_all_checks()
print(status)

# In FastAPI
@app.get("/health")
async def health():
    return await health_monitor.run_all_checks_async()
```

### 8. Use Async Translator

```python
from scalability.async_translator import AsyncRealtimeTranslator

# Create
translator = AsyncRealtimeTranslator(max_workers=4)
await translator.load_models()

# Single
original, translated = await translator.process_audio(audio_data)

# Batch
results = await translator.process_audio_batch([audio1, audio2, audio3])
```

### 9. Cache Translations

```python
from scalability.cache_manager import translation_cache

# Check cache
cached = translation_cache.get_translation(
    text="Hello",
    source_lang="en",
    target_lang="fra_Latn"
)

if not cached:
    # Translate
    translated = await translator.translate("Hello")
    
    # Cache it
    translation_cache.set_translation(
        text="Hello",
        source_lang="en",
        target_lang="fra_Latn",
        translation=translated,
        ttl=86400  # 24 hours
    )
```

---

## 🔧 Common Tasks

### Create API Key via API

```bash
curl -X POST "http://localhost:8000/auth/api-key" \
  -H "X-API-Key: ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "new_user", "tier": "pro"}'
```

### Test Translation

```bash
curl -X POST "http://localhost:8000/translate/text" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello World",
    "source_language": "en",
    "target_language": "fra_Latn"
  }'
```

### Check Health

```bash
curl http://localhost:8000/health
```

### View Metrics

```bash
curl http://localhost:8000/metrics
```

### Clear Cache

```bash
curl -X POST "http://localhost:8000/admin/cache/clear" \
  -H "X-API-Key: ADMIN_KEY"
```

### Reset Circuit Breakers

```bash
curl -X POST "http://localhost:8000/admin/circuit-breaker/reset" \
  -H "X-API-Key: ADMIN_KEY"
```

---

## 🚨 Troubleshooting

### Redis Connection Failed

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start Redis if not running
docker run -d -p 6379:6379 redis:alpine
```

### Import Errors

```bash
# Install missing dependencies
pip install -r requirements-production.txt

# Check Python path
export PYTHONPATH=$PYTHONPATH:/home/claude
```

### Circuit Breaker Open

```bash
# Check breaker status
curl http://localhost:8000/metrics

# Reset if needed
curl -X POST http://localhost:8000/admin/circuit-breaker/reset \
  -H "X-API-Key: ADMIN_KEY"
```

### Rate Limit Hit

```bash
# Check user's tier and limits
# In Redis:
redis-cli HGETALL "api_key:YOUR_KEY"

# Reset daily counter
redis-cli DEL "daily_limit:user:USER_ID:2024-01-15"
```

### High Memory Usage

```bash
# Clear cache
curl -X POST http://localhost:8000/admin/cache/clear \
  -H "X-API-Key: ADMIN_KEY"

# Check health
curl http://localhost:8000/health
```

---

## 📊 Performance Tuning

### For More Users

```python
# In rest_api_v2.py startup
translator = AsyncRealtimeTranslator(
    max_workers=16  # Increase for more concurrent requests
)
```

### For More Cache

```python
# In cache_manager.py
cache_manager = CacheManager(
    default_ttl=86400  # Increase TTL for longer cache
)
```

### For Faster Recovery

```python
# In circuit_breaker decorator
@circuit_breaker(
    failure_threshold=3,  # Lower = faster opening
    recovery_timeout=30   # Lower = faster recovery attempts
)
```

---

## 🔢 Rate Limits by Tier

| Tier | Requests/Minute | Requests/Day | Cost |
|------|-----------------|--------------|------|
| **Free** | 10 | 1,000 | $0 |
| **Basic** | 50 | 10,000 | $10/mo |
| **Pro** | 200 | 100,000 | $100/mo |
| **Enterprise** | 1,000 | 1,000,000 | Custom |

---

## 📈 Monitoring

### Key Metrics

```python
# Get all metrics
curl http://localhost:8000/metrics

# Returns:
{
  "translator": {
    "total_requests": 1234,
    "active_requests": 5,
    "max_concurrent": 12
  },
  "cache": {
    "hits": 456,
    "misses": 123,
    "hit_rate": 78.7
  },
  "circuit_breakers": [...]
}
```

### Health Status

```python
# Simple check (for load balancers)
curl http://localhost:8000/health/simple
# Returns: {"status": "healthy"}

# Detailed check
curl http://localhost:8000/health
# Returns: Full system status
```

---

## 🚀 Deploy to Production

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
```

```bash
docker-compose up -d
```

### NGINX Reverse Proxy

```nginx
# nginx.conf
upstream api {
    server api:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 💡 Pro Tips

1. **Always use HTTPS in production**
2. **Rotate API keys monthly**
3. **Monitor cache hit rate** (target: >40%)
4. **Set up alerts** on health endpoints
5. **Load test before going live**
6. **Keep Redis memory < 80%**
7. **Watch circuit breaker states**
8. **Log everything**
9. **Have rollback plan**
10. **Test recovery procedures**

---

## 📚 Full Documentation

- **Integration Guide:** `INTEGRATION_GUIDE.md`
- **Delivery Summary:** `DELIVERY_SUMMARY.md`
- **API Docs:** `http://localhost:8000/docs`
- **Code Examples:** In each file

---

## 🆘 Getting Help

1. Check logs: `docker-compose logs -f`
2. Check health: `curl /health`
3. Check metrics: `curl /metrics`
4. Reset cache: `curl -X POST /admin/cache/clear`
5. Reset breakers: `curl -X POST /admin/circuit-breaker/reset`

---

**Everything you need in one place!** 📋

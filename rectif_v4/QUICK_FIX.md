# ⚡ QUICK FIX - Railway Deployment (5 Minutes)

**Your deployment is failing due to 2 critical issues. Here's how to fix them NOW.**

---

## 🔴 Critical Fix #1: Redis Connection (2 minutes)

### Problem
Railway provides `REDIS_URL` but your app expects `REDIS_HOST` and `REDIS_PORT` separately.

### Solution
Add this code to `production/api.py` **after the imports, before creating the app**:

```python
# Add after imports section (around line 30-40)
from urllib.parse import urlparse

# Parse Railway's REDIS_URL
def configure_redis_from_railway():
    redis_url = os.getenv("REDIS_URL")
    if redis_url and not os.getenv("REDIS_HOST"):
        try:
            parsed = urlparse(redis_url)
            os.environ["REDIS_HOST"] = parsed.hostname or "localhost"
            os.environ["REDIS_PORT"] = str(parsed.port or 6379)
            if parsed.password:
                os.environ["REDIS_PASSWORD"] = parsed.password
            logger.info(f"✅ Redis configured from REDIS_URL")
        except Exception as e:
            logger.error(f"Failed to parse REDIS_URL: {e}")

# Call immediately
configure_redis_from_railway()
```

**Location**: Add right after this line in api.py:
```python
logger = logging.getLogger(__name__)

# ADD THE CODE HERE ← Right after logger setup
```

---

## 🔴 Critical Fix #2: Health Check Timeout (1 minute)

### Problem
Health checks timeout (60s) before models load (2-5 minutes).

### Solution

**Update `production/railway.toml`:**
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile.prod"

[deploy]
startCommand = "uvicorn api:app --host 0.0.0.0 --port $PORT --workers 1"
healthcheckPath = "/health/simple"
healthcheckTimeout = 300  # ← Change this to 300 (5 minutes)
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**OR manually in Railway Dashboard:**
1. Go to your service
2. Settings → Deploy
3. Health Check Path: `/health/simple`
4. Health Check Timeout: `300`
5. Click "Update"

---

## 🟡 Important Fix #3: Memory Optimization (30 seconds)

### Problem
Base model might exceed free tier memory (512MB).

### Solution

**Set in Railway Dashboard → Variables:**
```bash
WHISPER_MODEL=tiny
MAX_WORKERS=1
```

This reduces memory from ~300MB to ~150MB.

---

## 🚀 Deploy Now

### Option 1: Git Push (Auto-Deploy)
```bash
git add .
git commit -m "Fix Railway deployment"
git push origin main
```

### Option 2: Railway CLI
```bash
railway up
```

### Option 3: Railway Dashboard
Click "Deploy" button

---

## ✅ Verify Deployment

Wait 3-5 minutes, then test:

```bash
# Replace with your Railway URL
RAILWAY_URL="https://your-app.up.railway.app"

# 1. Health check
curl $RAILWAY_URL/health/simple

# Expected: {"status":"healthy","timestamp":"..."}
```

If successful, you'll see:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-06T..."
}
```

---

## 📊 Monitor Deployment

**Watch logs in real-time:**

```bash
# Using Railway CLI
railway logs --tail

# Or in Railway Dashboard
# Service → Deployments → View Logs
```

**Look for these success messages:**
```
✅ Configured Redis from REDIS_URL
✅ API started - models will load on first request
✅ Redis connected - caching enabled
```

---

## 🛑 If Still Failing

### Check Redis Connection

In Railway Dashboard:
1. Go to your Redis database
2. Copy the connection details
3. Manually set in Variables tab:
   ```bash
   REDIS_HOST=<hostname>
   REDIS_PORT=6379
   ```

### Check Logs for Errors

```bash
railway logs | grep ERROR
```

Common errors:
- `Connection refused` → Redis not configured
- `Health check failed` → Timeout too short
- `Out of memory` → Use WHISPER_MODEL=tiny

### Restart Deployment

```bash
railway up --detach
```

---

## 📞 Need Help?

If deployment still fails after these fixes:

1. **Share logs**: `railway logs > deployment.log`
2. **Check Railway status**: https://status.railway.app
3. **Discord**: https://discord.gg/railway

---

## ⏱️ Timeline

- **Fix code**: 2 minutes
- **Update config**: 1 minute  
- **Deploy**: 3-5 minutes
- **Test**: 1 minute

**Total**: ~10 minutes from fix to working API 🎉

---

## 🎯 Minimal Working Configuration

If you want the absolute minimal config that works:

**Environment Variables (Railway Dashboard):**
```bash
ENVIRONMENT=production
WHISPER_MODEL=tiny
MAX_WORKERS=1
JWT_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(32))">
ALLOWED_ORIGINS=*
```

**railway.toml:**
```toml
[deploy]
healthcheckPath = "/health/simple"
healthcheckTimeout = 300
```

**api.py** (add after imports):
```python
from urllib.parse import urlparse
redis_url = os.getenv("REDIS_URL")
if redis_url and not os.getenv("REDIS_HOST"):
    parsed = urlparse(redis_url)
    os.environ["REDIS_HOST"] = parsed.hostname
    os.environ["REDIS_PORT"] = str(parsed.port or 6379)
```

That's it! This is the bare minimum to get it working.

---

## ✨ Success Indicators

Deployment is successful when you see:

1. ✅ Build completes (3-4 minutes)
2. ✅ Health check passes (within 5 minutes)
3. ✅ `/health/simple` returns `{"status":"healthy"}`
4. ✅ Logs show "API ready to accept requests"
5. ✅ No error messages in logs

---

Good luck! Your deployment should work now. 🚀

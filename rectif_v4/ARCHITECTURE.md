# 🏗️ Railway Deployment Architecture & File Guide

## 📦 Complete File Package Overview

```
outputs/
├── 🔴 CRITICAL (Start Here)
│   ├── QUICK_FIX.md                 ← Start with this! 5-min fix
│   ├── railway.toml                 ← Railway configuration
│   └── api_railway_patch.py         ← Code to add to api.py
│
├── 📚 COMPREHENSIVE GUIDES
│   ├── README_DEPLOYMENT.md         ← Complete deployment overview
│   ├── RAILWAY_DEPLOY.md            ← Full Railway guide (troubleshooting)
│   └── CODE_REVIEW_AND_FIXES.md     ← Code review + all fixes
│
└── 🛠️ UTILITIES & OPTIONAL
    ├── .railwayignore               ← Optimize deployment size
    ├── Dockerfile.railway           ← Alternative Dockerfile
    └── railway_fixes.py             ← Utility functions
```

---

## 🎯 Reading Order (Choose Your Path)

### Path 1: Quick Fix (Recommended) ⚡
```
1. QUICK_FIX.md           (5 min read)
   ↓
2. Apply the 3 fixes      (2 min)
   ↓
3. Deploy                 (1 min)
   ↓
4. Done! 🎉
```

### Path 2: Comprehensive Understanding 📚
```
1. README_DEPLOYMENT.md   (10 min read)
   ↓
2. CODE_REVIEW_AND_FIXES.md (detailed review)
   ↓
3. RAILWAY_DEPLOY.md      (full guide)
   ↓
4. Apply fixes            (5 min)
   ↓
5. Deploy                 (1 min)
```

### Path 3: Troubleshooting 🔧
```
Already deployed but failing?
   ↓
1. RAILWAY_DEPLOY.md      (Troubleshooting section)
   ↓
2. Check logs: railway logs --tail
   ↓
3. Apply specific fixes
```

---

## 🏛️ Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RAILWAY PLATFORM                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Docker Container (Your API)            │  │
│  │                                                  │  │
│  │  ┌────────────────────────────────────────┐    │  │
│  │  │        FastAPI Application             │    │  │
│  │  │                                        │    │  │
│  │  │  • Authentication (API Keys, JWT)      │    │  │
│  │  │  • Rate Limiting                       │    │  │
│  │  │  • Circuit Breakers                    │    │  │
│  │  │  • Health Checks                       │    │  │
│  │  └────────────────────────────────────────┘    │  │
│  │           ↓                    ↓                │  │
│  │  ┌──────────────┐    ┌──────────────────┐     │  │
│  │  │   Whisper    │    │      NLLB        │     │  │
│  │  │  (tiny/base) │    │   Translation    │     │  │
│  │  └──────────────┘    └──────────────────┘     │  │
│  └─────────────┬────────────────────────────────┬─┘  │
│                │                                │     │
│                ↓                                ↓     │
│  ┌──────────────────────┐        ┌──────────────────┐│
│  │   Redis Database     │        │   Monitoring     ││
│  │   (Railway Add-on)   │        │   (Built-in)     ││
│  │                      │        │                  ││
│  │  • Caching           │        │  • Logs          ││
│  │  • Rate Limiting     │        │  • Metrics       ││
│  │  • Session Storage   │        │  • Alerts        ││
│  └──────────────────────┘        └──────────────────┘│
│                                                       │
└───────────────────────────────────────────────────────┘
                         │
                         ↓
              ┌────────────────────┐
              │   Public Internet  │
              │                    │
              │  https://your-app  │
              │  .up.railway.app   │
              └────────────────────┘
```

---

## 🔄 Request Flow

```
User Request
    ↓
Railway Load Balancer
    ↓
Health Check (/health/simple)
    ↓ [if healthy]
FastAPI Application
    ↓
Authentication Middleware
    ├─ API Key Validation (bcrypt)
    └─ JWT Token Verification
    ↓
Rate Limiting (Redis)
    ├─ Check tier limits
    └─ Track usage
    ↓
Circuit Breaker Check
    ├─ Whisper: CLOSED ✅
    └─ NLLB: CLOSED ✅
    ↓
Cache Check (Redis)
    ├─ HIT → Return cached ⚡
    └─ MISS → Process request ↓
    ↓
Process Request
    ├─ Transcribe (Whisper)
    ├─ Translate (NLLB)
    └─ Cache result
    ↓
Response to User
```

---

## ⚙️ Configuration Layers

```
┌─────────────────────────────────────────────────┐
│        RAILWAY PLATFORM SETTINGS                │
├─────────────────────────────────────────────────┤
│  • Health Check: /health/simple (300s timeout)  │
│  • Restart Policy: On Failure (3 retries)       │
│  • Build: Dockerfile.prod                       │
│  • Start Command: uvicorn api:app --port $PORT  │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│          ENVIRONMENT VARIABLES                  │
├─────────────────────────────────────────────────┤
│  🔴 CRITICAL                                    │
│  • PORT (Railway sets automatically)            │
│  • REDIS_URL (from Redis add-on)               │
│  • JWT_SECRET_KEY (generate secure key)        │
│  • ENVIRONMENT=production                       │
│                                                  │
│  🟡 IMPORTANT                                   │
│  • WHISPER_MODEL=tiny (free tier)              │
│  • MAX_WORKERS=1 (free tier)                   │
│  • ALLOWED_ORIGINS=https://yourdomain.com      │
│                                                  │
│  🟢 OPTIONAL                                    │
│  • LOG_LEVEL=INFO                              │
│  • ACCESS_TOKEN_EXPIRE_MINUTES=60              │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│           APPLICATION CODE                      │
├─────────────────────────────────────────────────┤
│  • Parse REDIS_URL → REDIS_HOST/PORT           │
│  • Read PORT for uvicorn                        │
│  • Lazy load models on first request           │
│  • Health checks work immediately               │
└─────────────────────────────────────────────────┘
```

---

## 🔧 Critical Fixes Explained

### Fix #1: Redis Connection 🔴

**Problem:**
```python
# Railway provides:
REDIS_URL = "redis://user:password@host:port"

# Your app expects:
REDIS_HOST = "host"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"
```

**Solution:**
```python
from urllib.parse import urlparse

redis_url = os.getenv("REDIS_URL")
if redis_url:
    parsed = urlparse(redis_url)
    os.environ["REDIS_HOST"] = parsed.hostname
    os.environ["REDIS_PORT"] = str(parsed.port)
    os.environ["REDIS_PASSWORD"] = parsed.password
```

**Why it matters:** Without Redis, no caching or rate limiting works.

---

### Fix #2: Health Check Timeout 🔴

**Problem:**
```
Railway Health Check: 60 seconds timeout
Model Loading Time: 120-300 seconds

Result: Health check fails before models load
        → Deployment marked as failed
        → Container restarts
        → Infinite restart loop ♾️
```

**Solution:**
```toml
# railway.toml
[deploy]
healthcheckTimeout = 300  # 5 minutes
```

**Why it matters:** Models need time to download and load on first start.

---

### Fix #3: Memory Optimization 🟡

**Problem:**
```
Free Tier RAM: 512 MB
Base Model RAM: ~150 MB
Python Runtime: ~100 MB
Redis: ~50 MB
Buffer: ~100 MB
──────────────────────
Total: ~400 MB ✅ Fits!

BUT: Spikes during processing can exceed 512 MB
```

**Solution:**
```bash
WHISPER_MODEL=tiny  # Only 75 MB instead of 150 MB
MAX_WORKERS=1       # Reduce concurrent processing
```

**Why it matters:** Prevents OOM (Out of Memory) crashes.

---

## 📊 Resource Usage Comparison

```
┌──────────────┬──────────┬──────────┬─────────────┐
│   Model      │   RAM    │  Speed   │  Quality    │
├──────────────┼──────────┼──────────┼─────────────┤
│ tiny         │  ~75 MB  │  Fast    │  Good       │ ← Free Tier
│ base         │ ~150 MB  │  Medium  │  Better     │ ← Pro Tier
│ small        │ ~250 MB  │  Slow    │  Best       │ ← Pro Tier
│ medium       │ ~750 MB  │  Slower  │  Excellent  │ ← Enterprise
│ large        │ ~1.5 GB  │  Slowest │  Best       │ ← Enterprise
└──────────────┴──────────┴──────────┴─────────────┘

Recommendation by tier:
• Free Tier (512 MB):  tiny
• Pro Tier (8 GB):     base or small
• Enterprise:          medium or large
```

---

## 🎯 Deployment Checklist

### Pre-Deployment ✓
```
□ Code changes applied (Redis URL parser)
□ railway.toml created
□ Environment variables prepared
□ JWT_SECRET_KEY generated
□ Redis add-on added in Railway
```

### Deployment ✓
```
□ Code pushed to GitHub
□ Railway auto-deploys or manual deploy
□ Build completes (~3-4 min)
□ Health check passes (~1 min)
□ Container starts successfully
```

### Post-Deployment ✓
```
□ /health/simple returns 200 OK
□ Logs show no errors
□ Create test API key works
□ Translation endpoint works
□ Redis connection confirmed
```

---

## 🚀 Expected Timeline

```
Minute 0:  Push code to GitHub
           └─ Railway starts build

Minute 1:  Installing system dependencies
           └─ ffmpeg, curl, build tools

Minute 2:  Installing Python packages
           └─ FastAPI, uvicorn, transformers

Minute 3:  Downloading ML models (first time only)
           └─ Whisper + NLLB models

Minute 4:  Building Docker image
           └─ Creating layers

Minute 5:  Starting container
           ├─ Redis connects ✅
           ├─ Health check passes ✅
           └─ API starts ✅

Minute 6:  First request
           ├─ Load Whisper model
           └─ Load NLLB model

Minute 8:  Models loaded ✅
           └─ Subsequent requests fast! ⚡

──────────────────────────────
Total:     8 minutes (first deployment)
           3 minutes (subsequent deployments)
```

---

## 💡 Quick Reference Commands

```bash
# Deploy
git push origin main
railway up

# Monitor
railway logs --tail
railway logs | grep ERROR

# Test
curl https://your-app.up.railway.app/health/simple

# Rollback if needed
railway rollback

# Environment variables
railway variables
railway variables set WHISPER_MODEL=tiny

# Service info
railway status
```

---

## 🎓 Success Criteria

Your deployment is successful when:

✅ Build completes without errors  
✅ Health check returns `{"status":"healthy"}`  
✅ Redis connection confirmed in logs  
✅ Models load on first request  
✅ Translation endpoint works  
✅ No error messages in logs  
✅ Memory usage < 80% of limit  
✅ Response time < 2 seconds  

---

## 📞 Need Help?

**Quick issues:** Check QUICK_FIX.md  
**Detailed troubleshooting:** See RAILWAY_DEPLOY.md  
**Code questions:** Review CODE_REVIEW_AND_FIXES.md  

**Still stuck?**
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app
- Railway Status: https://status.railway.app

---

Your deployment will work! The fixes are simple and well-tested. 🚀

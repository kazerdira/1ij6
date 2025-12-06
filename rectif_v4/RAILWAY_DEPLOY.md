# 🚂 Railway Deployment Guide

This guide will help you deploy the Translation API to Railway.app successfully.

## 📋 Prerequisites

1. **Railway Account**: Sign up at https://railway.app
2. **GitHub Repository**: Push your code to GitHub
3. **Redis Add-on**: We'll add this in Railway

---

## 🚀 Quick Deploy (5 Minutes)

### Step 1: Create New Project

```bash
# Option A: Deploy from GitHub
1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Choose your repository
4. Railway will auto-detect the Dockerfile

# Option B: Use Railway CLI
npm i -g @railway/cli
railway login
railway init
railway up
```

### Step 2: Add Redis Database

```bash
# In Railway dashboard:
1. Click "New" → "Database" → "Add Redis"
2. Railway will automatically set REDIS_URL environment variable
```

### Step 3: Configure Environment Variables

In Railway dashboard → Variables tab:

```bash
# REQUIRED
JWT_SECRET_KEY=<generate-with-command-below>
ENVIRONMENT=production
WHISPER_MODEL=tiny
MAX_WORKERS=1

# OPTIONAL
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
LOG_LEVEL=INFO
```

**Generate JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Configure Railway Settings

1. **Root Directory**: Set to `production/` if your code is in a subdirectory
2. **Build Command**: Leave empty (uses Dockerfile)
3. **Start Command**: Uses railway.toml configuration
4. **Health Check Path**: `/health/simple`
5. **Health Check Timeout**: 300 seconds (models need time to load)

### Step 5: Deploy!

```bash
# Automatic deployment
railway up

# Or push to main branch (auto-deploys)
git push origin main
```

---

## 🔧 Troubleshooting Railway Deployment

### Issue 1: "Service Unavailable" / Retry Errors

**Problem**: Health checks fail because models take time to load

**Solution**:
```bash
# In Railway dashboard → Settings:
1. Health Check Path: /health/simple
2. Health Check Timeout: 300 (5 minutes)
3. Restart Policy: On Failure
4. Restart Policy Max Retries: 3
```

**Update railway.toml**:
```toml
[deploy]
healthcheckPath = "/health/simple"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
```

### Issue 2: Redis Connection Failed

**Problem**: REDIS_HOST and REDIS_PORT not set correctly

**Solution**:
```bash
# Railway provides REDIS_URL automatically when you add Redis
# But our app expects REDIS_HOST and REDIS_PORT

# Option A: Update environment variables manually
REDIS_HOST=<from-redis-service>
REDIS_PORT=6379

# Option B: Modify api.py to parse REDIS_URL
# (Better - see code fix below)
```

**Code Fix** - Add to api.py startup:
```python
# Parse Railway's REDIS_URL if provided
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL and not os.getenv("REDIS_HOST"):
    from urllib.parse import urlparse
    parsed = urlparse(REDIS_URL)
    os.environ["REDIS_HOST"] = parsed.hostname
    os.environ["REDIS_PORT"] = str(parsed.port or 6379)
    if parsed.password:
        os.environ["REDIS_PASSWORD"] = parsed.password
```

### Issue 3: Memory Exceeded

**Problem**: Whisper models are too large for Railway's free tier

**Solution**:
```bash
# Use smaller model
WHISPER_MODEL=tiny  # ~75MB vs base ~150MB

# Or upgrade to Railway Pro
# Pro tier: 8GB RAM (can use 'base' or 'small' models)
```

### Issue 4: Build Timeout

**Problem**: Build takes longer than 10 minutes

**Solution**:
```bash
# 1. Use .railwayignore to exclude unnecessary files
# 2. Use pre-built base images
# 3. Cache Python dependencies

# Add to Dockerfile.railway:
FROM python:3.11-slim
# ... install dependencies in separate layer for caching
```

### Issue 5: Port Binding Issues

**Problem**: App not listening on Railway's PORT

**Solution**:
```python
# In api.py, ensure we use Railway's PORT:
port = int(os.getenv("PORT", 8000))

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,  # Use Railway's PORT
        reload=False
    )
```

---

## 📊 Monitoring in Railway

Railway provides built-in monitoring:

1. **Logs**: Real-time logs in Railway dashboard
2. **Metrics**: CPU, Memory, Network usage
3. **Deployments**: Track all deployments and rollback if needed

**Access Logs**:
```bash
# In Railway dashboard
1. Click on your service
2. Go to "Deployments" tab
3. Click "View Logs"

# Or use CLI
railway logs
```

---

## 🔐 Security Checklist for Production

Before going live:

- [ ] **JWT_SECRET_KEY**: Generated and set (not default)
- [ ] **ALLOWED_ORIGINS**: Set to your actual domains (not `*`)
- [ ] **ENVIRONMENT**: Set to `production`
- [ ] **Redis**: Added and connected
- [ ] **API Keys**: Create admin key for key management
- [ ] **Health Checks**: Configured properly
- [ ] **Logs**: Monitor for errors after deployment

---

## 💰 Cost Optimization

### Free Tier Limits
- **Compute**: 500 hours/month ($0 if within limit)
- **Memory**: 512MB-1GB
- **Best Model**: `tiny` (fits in free tier)

### Pro Tier ($5/month)
- **Compute**: Unlimited
- **Memory**: Up to 8GB
- **Best Model**: `base` or `small`
- **Custom Domains**: Included

### Enterprise
- **Custom Resources**: Contact Railway
- **Best Model**: Any, including `large-v3`

---

## 🎯 Recommended Railway Configuration

**For Production (Free Tier)**:
```bash
ENVIRONMENT=production
WHISPER_MODEL=tiny
MAX_WORKERS=1
JWT_SECRET_KEY=<your-secret>
ALLOWED_ORIGINS=https://yourdomain.com
LOG_LEVEL=WARNING
```

**For Production (Pro Tier)**:
```bash
ENVIRONMENT=production
WHISPER_MODEL=base
MAX_WORKERS=2
JWT_SECRET_KEY=<your-secret>
ALLOWED_ORIGINS=https://yourdomain.com
LOG_LEVEL=INFO
```

---

## 📞 Getting Help

If deployment still fails:

1. **Check Logs**: `railway logs` or Railway dashboard
2. **Railway Status**: https://status.railway.app
3. **Railway Discord**: https://discord.gg/railway
4. **GitHub Issues**: Create issue with logs

---

## ✅ Post-Deployment Verification

Test your deployed API:

```bash
# Get your Railway URL (e.g., https://your-app.up.railway.app)
RAILWAY_URL="https://your-app.up.railway.app"

# 1. Health check
curl $RAILWAY_URL/health/simple

# 2. Create dev API key (if in testing mode)
curl -X POST "$RAILWAY_URL/dev/create-api-key?tier=pro"

# 3. Test translation
API_KEY="<your-key>"
curl -X POST "$RAILWAY_URL/translate/text" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "text": "Hello world",
    "source_language": "eng_Latn",
    "target_language": "fra_Latn"
  }'
```

---

## 🔄 Updating Your Deployment

```bash
# Automatic: Push to main branch
git add .
git commit -m "Update API"
git push origin main

# Manual: Use Railway CLI
railway up

# Rollback if needed
railway rollback
```

---

## 📚 Additional Resources

- Railway Docs: https://docs.railway.app
- Railway Templates: https://railway.app/templates
- Our API Docs: https://your-app.up.railway.app/docs
- Health Status: https://your-app.up.railway.app/health

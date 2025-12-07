# TranslateAPI Dashboard

Full-stack dashboard with authentication, API key management, and usage tracking.

## Tech Stack

- **Frontend:** Next.js 14 (App Router) + Tailwind CSS
- **Backend:** Next.js API Routes
- **Database:** Supabase (PostgreSQL)
- **Auth:** Supabase Auth
- **GPU Backend:** RunPod Serverless

## Setup

### 1. Install Dependencies

```bash
cd dashboard
npm install
```

### 2. Setup Supabase Database

1. Go to your Supabase project: https://supabase.com/dashboard/project/ipyepuvljbniljjizimm
2. Go to **SQL Editor**
3. Copy the contents of `../supabase/schema.sql`
4. Paste and click **Run**

### 3. Get Supabase Service Role Key

1. Go to **Settings → API**
2. Copy the `service_role` key (secret, under "Project API keys")
3. Add it to `.env.local`:

```env
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

### 4. Configure Supabase Auth

1. Go to **Authentication → URL Configuration**
2. Set Site URL: `http://localhost:3000` (for dev)
3. Add Redirect URL: `http://localhost:3000/auth/callback`

### 5. Run Development Server

```bash
npm run dev
```

Visit http://localhost:3000

## Deploy to Vercel

### 1. Push to GitHub

```bash
git add dashboard/
git commit -m "Add dashboard with Supabase auth"
git push
```

### 2. Deploy on Vercel

1. Go to https://vercel.com
2. Import your GitHub repo
3. Set Root Directory: `dashboard`
4. Add Environment Variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `RUNPOD_API_KEY`
5. Deploy

### 3. Update Supabase Auth URLs

After deployment, update Supabase:
1. Go to **Authentication → URL Configuration**
2. Set Site URL: `https://your-app.vercel.app`
3. Add Redirect URL: `https://your-app.vercel.app/auth/callback`

## API Endpoints

The dashboard includes a complete API gateway:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/translate` | POST | Translate text |
| `/api/v1/transcribe` | POST | Transcribe + translate audio |

### Example Usage

```bash
curl -X POST "https://your-app.vercel.app/api/v1/translate" \
  -H "Authorization: Bearer sk_live_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world!",
    "source_lang": "eng_Latn",
    "target_lang": "fra_Latn"
  }'
```

## Architecture

```
User Request → Vercel (API Gateway)
                   ↓
              Validate API Key (Supabase)
                   ↓
              Check Rate Limits (Supabase)
                   ↓
              Forward to RunPod (GPU)
                   ↓
              Record Usage (Supabase)
                   ↓
              Return Response
```

## Features

- ✅ User signup/login
- ✅ API key generation
- ✅ Usage tracking
- ✅ Rate limiting by tier
- ✅ Monthly quotas
- ✅ Recent activity log
- ✅ Responsive design

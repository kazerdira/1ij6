# TranslateAPI Landing Page

This folder contains the GitHub Pages landing page for the TranslateAPI service.

## Files

- `index.html` - Main landing page
- `docs.html` - API documentation

## Deployment

### Option 1: GitHub Pages (Free)

1. Push this folder to your GitHub repository
2. Go to Settings → Pages
3. Source: Deploy from branch
4. Branch: `master` (or `main`)
5. Folder: `/docs`
6. Save

Your site will be live at: `https://kazerdira.github.io/1ij6/`

### Option 2: Custom Domain (Optional, ~$10/year)

1. Buy a domain (Namecheap, Porkbun, etc.)
2. Add a CNAME file with your domain
3. Configure DNS:
   - CNAME: `www` → `kazerdira.github.io`
   - A records: GitHub's IPs (185.199.108-111.153)
4. Enable "Enforce HTTPS" in GitHub Pages settings

## Customization

### Update API URL
Replace placeholder URLs in both files:
- Current: `https://api.translateapi.dev/v1`
- Replace with your actual RunPod endpoint or custom domain

### Update Contact Form
Replace `https://forms.gle/YOUR_FORM_ID` with your actual Google Form link.

### Update Email
Replace `your-email@example.com` with your actual email.

## Local Development

Open `index.html` directly in a browser, or use a simple server:

```bash
# Python
python -m http.server 8000

# Node.js
npx serve .
```

Then visit `http://localhost:8000`

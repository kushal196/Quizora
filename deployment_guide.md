# Quizora Web App Deployment Guide

## Prerequisites
- Your Flask application is working locally
- You have a domain name (optional but recommended)
- Google OAuth credentials configured for production

## Option 1: Railway (Recommended - Easy & Free)

### Step 1: Prepare Your App
1. Create a `Procfile` in your root directory:
```
web: gunicorn app:app
```

2. Create a `runtime.txt` file:
```
python-3.9.18
```

3. Update `requirements.txt`:
```
Flask==2.3.3
Werkzeug==2.3.7
reportlab==4.0.4
requests==2.31.0
gunicorn==21.2.0
```

### Step 2: Deploy to Railway
1. Go to [Railway](https://railway.app/)
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Railway will automatically detect it's a Python app
6. Add environment variables:
   - `SECRET_KEY`: Generate a random secret key
   - `GOOGLE_CLIENT_ID`: Your Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET`: Your Google OAuth client secret
   - `GOOGLE_REDIRECT_URI`: `https://your-app-name.railway.app/google/callback`

### Step 3: Update Google OAuth
1. Go to Google Cloud Console
2. Add your Railway domain to authorized redirect URIs:
   - `https://your-app-name.railway.app/google/callback`

## Option 2: Render (Free Tier Available)

### Step 1: Prepare Your App
1. Create a `render.yaml` file:
```yaml
services:
  - type: web
    name: quizora
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: GOOGLE_CLIENT_SECRET
        sync: false
      - key: GOOGLE_REDIRECT_URI
        value: https://your-app-name.onrender.com/google/callback
```

### Step 2: Deploy to Render
1. Go to [Render](https://render.com/)
2. Sign up and connect your GitHub
3. Click "New" → "Web Service"
4. Select your repository
5. Configure environment variables
6. Deploy

## Option 3: Heroku (Paid)

### Step 1: Prepare Your App
1. Install Heroku CLI
2. Create `Procfile`:
```
web: gunicorn app:app
```

3. Update `requirements.txt` with gunicorn

### Step 2: Deploy
```bash
heroku create your-app-name
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

## Option 4: DigitalOcean App Platform

### Step 1: Prepare Your App
1. Create `.do/app.yaml`:
```yaml
name: quizora
services:
- name: web
  github:
    branch: main
    deploy_on_push: true
    repo: your-username/your-repo
  run_command: gunicorn app:app
  environment_slug: python
  envs:
  - key: SECRET_KEY
    value: your-secret-key
  - key: GOOGLE_CLIENT_ID
    value: your-google-client-id
  - key: GOOGLE_CLIENT_SECRET
    value: your-google-client-secret
  - key: GOOGLE_REDIRECT_URI
    value: https://your-app-name.ondigitalocean.app/google/callback
```

### Step 2: Deploy
1. Go to DigitalOcean App Platform
2. Connect your GitHub repository
3. Configure environment variables
4. Deploy

## Option 5: VPS (DigitalOcean, AWS, etc.)

### Step 1: Set Up Server
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, Nginx, and other dependencies
sudo apt install python3 python3-pip nginx sqlite3 -y

# Install Gunicorn
pip3 install gunicorn
```

### Step 2: Deploy Your App
```bash
# Clone your repository
git clone https://github.com/your-username/your-repo.git
cd your-repo

# Install dependencies
pip3 install -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/quizora.service
```

### Step 3: Create Service File
```ini
[Unit]
Description=Quizora Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/quizora
Environment="PATH=/var/www/quizora/venv/bin"
ExecStart=/var/www/quizora/venv/bin/gunicorn --workers 3 --bind unix:quizora.sock -m 007 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Step 4: Configure Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/quizora/quizora.sock;
    }
}
```

## Environment Variables Setup

Create a `.env` file for local development:
```env
SECRET_KEY=your-secret-key-here
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.com/google/callback
```

## Production Checklist

### 1. Security
- [ ] Set `SECRET_KEY` environment variable
- [ ] Enable HTTPS (SSL certificate)
- [ ] Configure proper CORS settings
- [ ] Set up rate limiting
- [ ] Use environment variables for sensitive data

### 2. Database
- [ ] Consider using PostgreSQL for production
- [ ] Set up database backups
- [ ] Configure connection pooling

### 3. Performance
- [ ] Use Gunicorn with multiple workers
- [ ] Set up CDN for static files
- [ ] Enable caching
- [ ] Configure logging

### 4. Monitoring
- [ ] Set up error tracking (Sentry)
- [ ] Configure uptime monitoring
- [ ] Set up log aggregation

## Google OAuth Production Setup

### 1. Update OAuth Consent Screen
1. Go to Google Cloud Console
2. Add your production domain to authorized domains
3. Add production redirect URIs
4. Publish the app (if ready)

### 2. Update Environment Variables
```python
# In app.py, update for production
GOOGLE_REDIRECT_URI = "https://your-domain.com/google/callback"
```

## Troubleshooting

### Common Issues:
1. **Static files not loading**: Configure static file serving
2. **Database errors**: Check file permissions and paths
3. **OAuth redirect errors**: Verify redirect URIs match exactly
4. **Import errors**: Ensure all dependencies are in requirements.txt

### Debug Commands:
```bash
# Check logs
heroku logs --tail  # For Heroku
railway logs        # For Railway
render logs         # For Render

# Check environment variables
heroku config       # For Heroku
railway variables   # For Railway
```

## Recommended for Beginners:
1. **Railway** - Easiest to set up, good free tier
2. **Render** - Simple deployment, reliable
3. **Heroku** - Most documentation, but paid

## Cost Comparison:
- **Railway**: Free tier available, then $5/month
- **Render**: Free tier available, then $7/month
- **Heroku**: $7/month minimum
- **DigitalOcean**: $5/month for basic droplet
- **VPS**: $3-10/month depending on provider

Choose based on your budget and technical expertise! 
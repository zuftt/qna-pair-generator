# Deployment Guide for QnA Pair Generator

This guide covers deploying the QnA Pair Generator to production on your domain.

## Prerequisites

- A domain name (e.g., `yourdomain.com`)
- A server/hosting service (VPS, cloud provider, etc.)
- Python 3.8+ installed on the server
- Terminal/SSH access to your server

## Deployment Options

### Option 1: VPS/Cloud Server (Recommended for production)

Best for: Professional deployment, full control, secure environments

#### Setup Steps:

1. **Connect to your server via SSH**
   ```bash
   ssh user@your-server-ip
   ```

2. **Install dependencies**
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-pip nginx
   ```

3. **Clone your repository**
   ```bash
   cd /var/www
   git clone https://github.com/zuftt/qna-pair-generator.git
   cd qna-pair-generator
   ```

4. **Set up Python virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn  # Production WSGI server
   ```

5. **Configure environment variables**
   ```bash
   nano .env
   ```
   Add your configuration:
   ```env
   OPENAI_API_KEY=your_api_key_here
   OPENAI_BASE_URL=https://openrouter.ai/api/v1
   QWEN_GEN_MODEL=qwen/qwen3-30b-a3b:free
   QWEN_REVIEW_MODEL=qwen/qwen3-30b-a3b:free
   ```

6. **Create Gunicorn service**
   ```bash
   sudo nano /etc/systemd/system/qna-pair-gen.service
   ```
   
   Add this configuration:
   ```ini
   [Unit]
   Description=QnA Pair Generator Web App
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/qna-pair-generator
   Environment="PATH=/var/www/qna-pair-generator/venv/bin"
   ExecStart=/var/www/qna-pair-generator/venv/bin/gunicorn --bind unix:/var/www/qna-pair-generator/qna-pair-gen.sock --workers 4 web:app

   [Install]
   WantedBy=multi-user.target
   ```

7. **Start the service**
   ```bash
   sudo systemctl start qna-pair-gen
   sudo systemctl enable qna-pair-gen
   sudo systemctl status qna-pair-gen
   ```

8. **Configure Nginx reverse proxy**
   ```bash
   sudo nano /etc/nginx/sites-available/qna-pair-gen
   ```
   
   Add this configuration:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com www.yourdomain.com;

       location / {
           include proxy_params;
           proxy_pass http://unix:/var/www/qna-pair-generator/qna-pair-gen.sock;
           proxy_read_timeout 300;
           proxy_connect_timeout 300;
           proxy_send_timeout 300;
       }

       client_max_body_size 16M;  # Allow file uploads up to 16MB
   }
   ```

9. **Enable the site and test**
   ```bash
   sudo ln -s /etc/nginx/sites-available/qna-pair-gen /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

10. **Set up SSL certificate (Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

11. **Update DNS records**
   Point your domain to your server's IP address:
   - A record: `@` → your-server-ip
   - A record: `www` → your-server-ip

---

### Option 2: Railway.app

Best for: Quick deployment, managed infrastructure, auto-scaling

#### Setup Steps:

1. **Install Railway CLI** (optional, can use web UI)
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize project**
   ```bash
   cd qna-pair-generator
   railway init
   ```

4. **Create Procfile** (create in project root)
   ```
   web: gunicorn --bind 0.0.0.0:$PORT --workers 4 web:app
   ```

5. **Set environment variables** (via Railway dashboard or CLI)
   ```bash
   railway variables set OPENAI_API_KEY=your_api_key
   railway variables set OPENAI_BASE_URL=https://openrouter.ai/api/v1
   railway variables set QWEN_GEN_MODEL=qwen/qwen3-30b-a3b:free
   railway variables set QWEN_REVIEW_MODEL=qwen/qwen3-30b-a3b:free
   ```

6. **Deploy**
   ```bash
   railway up
   ```

7. **Custom domain** (in Railway dashboard)
   - Go to Settings → Domains
   - Add your custom domain
   - Update DNS records as instructed

---

### Option 3: Render.com

Best for: Easy deployment, free tier available, auto-deploy from GitHub

#### Setup Steps:

1. **Sign up** at https://render.com

2. **Connect GitHub repository**

3. **Create a new Web Service**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn web:app`
   - Environment: Python 3

4. **Add environment variables** (in dashboard)
   - `OPENAI_API_KEY`: your key
   - `OPENAI_BASE_URL`: https://openrouter.ai/api/v1
   - `QWEN_GEN_MODEL`: qwen/qwen3-30b-a3b:free
   - `QWEN_REVIEW_MODEL`: qwen/qwen3-30b-a3b:free

5. **Set up custom domain** (in dashboard)
   - Go to Settings → Custom Domains
   - Add domain and follow DNS instructions

6. **Enable auto-deploy** (optional)
   - Connect to GitHub branch
   - Auto-deploy on push

---

### Option 4: DigitalOcean App Platform

Best for: Managed platform, integrated with DigitalOcean ecosystem

#### Setup Steps:

1. **Create a new App** in DigitalOcean dashboard

2. **Connect GitHub repository**

3. **Configure build settings**
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `gunicorn web:app`

4. **Add environment variables**
   - Same variables as other platforms

5. **Set up custom domain**
   - Add domain in App Settings
   - Update DNS records

---

## Important Production Settings

### Security Considerations

1. **Never commit `.env` file**
   - Already in `.gitignore`
   - Use environment variables on hosting platform

2. **Use strong API keys**
   - Rotate keys periodically
   - Monitor API usage

3. **Enable HTTPS**
   - Force SSL redirect
   - Use Let's Encrypt for free certificates

4. **Configure CORS** (if needed for API access)
   Add to `web.py`:
   ```python
   from flask_cors import CORS
   CORS(app)  # Configure as needed for your use case
   ```

### Performance Optimization

1. **Gunicorn workers**
   ```bash
   gunicorn --workers 4 --threads 2 --timeout 300 web:app
   ```

2. **Nginx caching** (for static assets)
   ```nginx
   location /static {
       alias /path/to/static;
       expires 30d;
   }
   ```

3. **Database** (if scaling)
   - Consider Redis for caching
   - PostgreSQL/MySQL for user data (if adding auth)

---

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check if Gunicorn is running: `sudo systemctl status qna-pair-gen`
   - Check logs: `sudo journalctl -u qna-pair-gen -f`

2. **File upload errors**
   - Increase `client_max_body_size` in Nginx
   - Check file permissions

3. **API errors**
   - Verify environment variables are set
   - Check API key validity
   - Monitor rate limits

4. **Connection timeouts**
   - Increase timeout values in Gunicorn and Nginx
   - Check server resources (CPU, memory)

### Logs

**Gunicorn logs:**
```bash
sudo journalctl -u qna-pair-gen -f
```

**Nginx logs:**
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

**Application logs:**
```bash
tail -f /var/www/qna-pair-generator/app.log  # If configured
```

---

## Monitoring

### Set up monitoring (recommended)

1. **Health check endpoint** (already exists: `/api/health`)
   ```bash
   curl https://yourdomain.com/api/health
   ```

2. **Uptime monitoring**
   - Use services like UptimeRobot, Pingdom, or BetterUptime
   - Set alerts for downtime

3. **Error tracking**
   - Consider Sentry for production error tracking

---

## Updates and Maintenance

### Deploy updates

```bash
cd /var/www/qna-pair-generator
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # If dependencies changed
sudo systemctl restart qna-pair-gen
```

### Backup strategy

- Regular backups of:
  - Code repository (Git)
  - Environment variables
  - Server configuration files

---

## Cost Estimates

- **VPS**: $5-20/month (DigitalOcean, Linode, Vultr)
- **Railway**: $5+/month (usage-based)
- **Render**: Free tier available, $7+/month for production
- **DigitalOcean**: $5-25/month (App Platform)

---

## Need Help?

If you encounter issues during deployment:

1. Check logs (listed above)
2. Review this guide carefully
3. Visit project GitHub issues: https://github.com/zuftt/qna-pair-generator/issues
4. Contact the maintainer

---

## Quick Reference

**Local development:**
```bash
python3 web.py
```

**Production with Gunicorn:**
```bash
gunicorn --bind 0.0.0.0:8000 --workers 4 web:app
```

**With Nginx (production):**
```bash
gunicorn --bind unix:/path/to/sock --workers 4 web:app
```

---

Good luck with your deployment! 🚀


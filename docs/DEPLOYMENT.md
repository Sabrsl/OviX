# Deployment Guide

## Overview

This guide covers deployment options for the Wikipedia Maintenance Tool, from local development to production environments.

## Deployment Options

### 1. Local Development

For local development and testing:

```bash
# Activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

The application will be available at `http://localhost:8501`

### 2. Docker Deployment

#### Building the Docker Image

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data logs config

# Expose Streamlit port
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build the image:

```bash
docker build -t wikipedia-maintenance-tool .
```

#### Running with Docker

```bash
docker run -d \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  wikipedia-maintenance-tool
```

#### Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
    restart: unless-stopped
```

Run with Docker Compose:

```bash
docker-compose up -d
```

### 3. Cloud Deployment

#### Streamlit Cloud

1. Push your code to a GitHub repository
2. Go to [Streamlit Cloud](https://share.streamlit.io/)
3. Click "New app"
4. Connect your GitHub repository
5. Configure deployment settings
6. Click "Deploy"

**Important**: For Streamlit Cloud, you'll need to:
- Add `user-config.py` as a secret (don't commit it to git)
- Configure environment variables for sensitive data
- Use a persistent storage solution for the database

#### Heroku

Create a `Procfile`:

```
web: streamlit run app.py --server.port=$PORT
```

Create a `runtime.txt`:

```
python-3.12
```

Deploy to Heroku:

```bash
heroku create your-app-name
git push heroku main
```

#### AWS EC2

1. Launch an EC2 instance (Ubuntu recommended)
2. SSH into the instance
3. Install dependencies:

```bash
sudo apt update
sudo apt install python3.12 python3-pip git
```

4. Clone your repository
5. Set up virtual environment and install dependencies
6. Run with a process manager (systemd or supervisor)

**Systemd Service Example**:

Create `/etc/systemd/system/wikipedia-maintenance.service`:

```ini
[Unit]
Description=Wikipedia Maintenance Tool
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/wikipedia-maintenance-tool
Environment="PATH=/home/ubuntu/wikipedia-maintenance-tool/venv/bin"
ExecStart=/home/ubuntu/wikipedia-maintenance-tool/venv/bin/streamlit run app.py --server.port=8501
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable wikipedia-maintenance
sudo systemctl start wikipedia-maintenance
```

### 4. Reverse Proxy (Nginx)

For production deployments, use Nginx as a reverse proxy:

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

Enable SSL with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Security Considerations

### 1. Environment Variables

Store sensitive configuration in environment variables:

```bash
export WIKIPEDIA_USERNAME="your_username"
export WIKIPEDIA_PASSWORD="your_password"
```

Use a `.env` file (add to `.gitignore`):

```env
WIKIPEDIA_USERNAME=your_username
WIKIPEDIA_PASSWORD=your_password
```

Load in Python:

```python
from dotenv import load_dotenv
load_dotenv()
```

### 2. Firewall Configuration

Restrict access to the application:

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Authentication

Add authentication to protect the application:

#### Basic Authentication with Nginx

```bash
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

Update Nginx configuration:

```nginx
auth_basic "Restricted Access";
auth_basic_user_file /etc/nginx/.htpasswd;
```

#### Streamlit Authentication

Use Streamlit's built-in authentication (requires Streamlit Pro or custom implementation):

```python
import streamlit as st

# Add to app.py
st.auth("username", "password")
```

### 4. HTTPS

Always use HTTPS in production:
- Use Let's Encrypt for free SSL certificates
- Configure proper SSL settings
- Enable HSTS

## Monitoring and Logging

### 1. Application Logs

Logs are stored in `logs/wikipedia-maintenance.log`. Configure log rotation:

```bash
# Logrotate configuration
/home/ubuntu/wikipedia-maintenance-tool/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### 2. Process Monitoring

Monitor the application process:

```bash
# Check if running
sudo systemctl status wikipedia-maintenance

# View logs
sudo journalctl -u wikipedia-maintenance -f
```

### 3. Database Backups

Set up automated database backups:

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
cp data/wikipedia_maintenance.db backups/wikipedia_maintenance_$DATE.db
find backups/ -name "wikipedia_maintenance_*.db" -mtime +7 -delete
```

Add to crontab:

```bash
0 2 * * * /path/to/backup.sh
```

## Performance Optimization

### 1. Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[logger]
level = "info"
```

### 2. Caching

Implement caching for frequently accessed data:

```python
@st.cache_data(ttl=3600)
def get_article_content(title):
    # Cache for 1 hour
    pass
```

### 3. Database Optimization

- Add indexes to frequently queried columns
- Regularly vacuum the SQLite database
- Consider migrating to PostgreSQL for high-volume deployments

## Scaling Considerations

### Horizontal Scaling

For multiple instances:
- Use a shared database (PostgreSQL instead of SQLite)
- Implement session management
- Use a load balancer

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Optimize database queries
- Implement connection pooling

## Backup and Recovery

### Database Backup

```bash
# Backup
sqlite3 data/wikipedia_maintenance.db ".backup data/backup.db"

# Restore
cp data/backup.db data/wikipedia_maintenance.db
```

### Configuration Backup

```bash
# Backup configuration
tar -czf config_backup.tar.gz config/

# Restore
tar -xzf config_backup.tar.gz
```

## Troubleshooting

### Application Won't Start

1. Check logs: `logs/wikipedia-maintenance.log`
2. Verify dependencies: `pip list`
3. Check port availability: `netstat -tlnp | grep 8501`
4. Verify configuration: `config/config.yaml`

### Database Issues

1. Check database file permissions
2. Verify SQLite integrity: `sqlite3 data/wikipedia_maintenance.db "PRAGMA integrity_check;"`
3. Restore from backup if corrupted

### Performance Issues

1. Monitor resource usage: `htop`
2. Check database size
3. Review logs for errors
4. Consider increasing server resources

## Maintenance

### Regular Tasks

- **Daily**: Review logs, check errors
- **Weekly**: Database backup, review statistics
- **Monthly**: Update dependencies, review configuration
- **Quarterly**: Security audit, performance review

### Updates

Update the application:

```bash
git pull origin main
pip install -r requirements.txt --upgrade
sudo systemctl restart wikipedia-maintenance
```

## Support

For deployment issues:
1. Check the logs
2. Review this documentation
3. Consult the Streamlit documentation
4. Check Pywikibot documentation
5. Contact support

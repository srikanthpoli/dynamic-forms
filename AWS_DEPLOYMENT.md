# AWS Deployment Guide

This guide deploys the Dynamic Forms application using:

```text
Browser -> Nginx on EC2 -> Angular frontend
                         -> FastAPI at 127.0.0.1:8000
                              -> Amazon RDS PostgreSQL
```

Do not commit `.env`, private keys, passwords, or API keys.

## 1. AWS resources

Create or verify:

- EC2 Ubuntu instance with a public IPv4 address
- RDS PostgreSQL database
- EC2 security group allowing:
  - SSH TCP 22 from your IP only
  - HTTP TCP 80 from `0.0.0.0/0`
  - HTTPS TCP 443 from `0.0.0.0/0`
- RDS security group allowing TCP 5432 from the EC2 security group

Do not expose RDS port 5432 publicly. Port 8000 is only for temporary testing and should not be publicly exposed after Nginx is working.

## 2. Connect to EC2 from Windows

```powershell
ssh -i "C:\path\to\dynamicforms_aws.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

Use the current EC2 public IP. It can change after stop/start unless an Elastic IP is attached.

## 3. Prepare EC2 storage

The embedding model and PyTorch need memory and disk space. Use an EBS volume of at least 20 GB.

Check storage:

```bash
df -h /
lsblk
```

If the disk was enlarged but the root partition was not:

```bash
sudo apt update
sudo apt install -y cloud-guest-utils
sudo growpart /dev/nvme0n1 1
sudo resize2fs /dev/nvme0n1p1
df -h /
```

Add swap on small instances:

```bash
sudo fallocate -l 3G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

## 4. Install EC2 packages

```bash
sudo apt update
sudo apt install -y curl git nginx python3 python3-venv postgresql-client unzip build-essential
```

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv --version
```

## 5. Get the project

```bash
cd ~
git clone https://github.com/srikanthpoli/dynamic-forms.git
auto_dir=dynamic-forms
cd ~/dynamic-forms/backend
```

If the repository already exists, update it instead:

```bash
cd ~/dynamic-forms
git pull
```

## 6. Create the server environment file

The backend reads only a file named exactly `.env` in the `backend` directory:

```bash
cd ~/dynamic-forms/backend
nano .env
chmod 600 .env
```

Use placeholders filled with your private values:

```env
LOG_LEVEL=INFO
LLM_PROVIDER=grok
XAI_API_KEY=YOUR_ROTATED_XAI_KEY
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.20-0309-non-reasoning
AWS_REGION=us-east-1
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHROMA_PERSIST_DIR=app/data/chroma
MATERIAL_SPEC_PATH=app/data/angular_material_capabilities.json
DATABASE_URL=postgresql+psycopg2://RDS_USER:RDS_PASSWORD@RDS_ENDPOINT:5432/RDS_DATABASE
CORS_ORIGINS=["http://YOUR_EC2_PUBLIC_IP"]
```

If Nginx serves both frontend and API from the same origin, `CORS_ORIGINS` can use the site origin or `[*]` for temporary testing. Prefer the exact origin in production.

Never put real values in this documentation or Git.

## 7. Install and run FastAPI

```bash
cd ~/dynamic-forms/backend
rm -rf .venv
uv cache clean
uv venv --python 3
source .venv/bin/activate
uv sync
```

Test RDS connectivity:

```bash
psql "$DATABASE_URL" -c "SELECT version();"
```

Run the backend temporarily:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another SSH session:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

## 8. Run FastAPI as a system service

Stop the temporary Uvicorn process with `Ctrl+C`, then create the service:

```bash
sudo nano /etc/systemd/system/dynamic-forms-api.service
```

Paste:

```ini
[Unit]
Description=Dynamic Forms FastAPI backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/dynamic-forms/backend
EnvironmentFile=/home/ubuntu/dynamic-forms/backend/.env
ExecStart=/home/ubuntu/dynamic-forms/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dynamic-forms-api
sudo systemctl status dynamic-forms-api
```

View logs:

```bash
sudo journalctl -u dynamic-forms-api -f
```

## 9. Build the Angular frontend locally

On Windows PowerShell:

```powershell
cd "E:\path\to\Dynamic_Forms\frontend"
npm install
npm run build
```

The production files are generated under:

```text
frontend/dist/dynamic-forms-frontend/browser
```

The Angular API configuration uses:

- Local browser hosts: `http://127.0.0.1:8000/api`
- Deployed hosts: `/api`

This lets Nginx proxy API calls without exposing port 8000 to browsers.

## 10. Upload the frontend

From Windows PowerShell:

```powershell
cd "E:\path\to\Dynamic_Forms\frontend"
Compress-Archive `
  -Path ".\dist\dynamic-forms-frontend\browser\*" `
  -DestinationPath ".\dynamic-forms-ui.zip" `
  -Force

scp -i "C:\path\to\dynamicforms_aws.pem" `
  ".\dynamic-forms-ui.zip" `
  ubuntu@YOUR_EC2_PUBLIC_IP:/tmp/dynamic-forms-ui.zip
```

On EC2:

```bash
rm -rf /tmp/dynamic-forms-ui-new
mkdir -p /tmp/dynamic-forms-ui-new
unzip -q /tmp/dynamic-forms-ui.zip -d /tmp/dynamic-forms-ui-new
sudo rm -rf /var/www/dynamic-forms/*
sudo mkdir -p /var/www/dynamic-forms
sudo cp -r /tmp/dynamic-forms-ui-new/* /var/www/dynamic-forms/
```

## 11. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/dynamic-forms
```

Paste:

```nginx
server {
    listen 80 default_server;
    server_name _;

    root /var/www/dynamic-forms;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Enable it:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/dynamic-forms /etc/nginx/sites-enabled/dynamic-forms
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl restart nginx
```

## 12. Verify the deployment

On EC2:

```bash
curl http://127.0.0.1/
curl http://127.0.0.1/health
curl http://127.0.0.1/api/fields/
curl http://127.0.0.1/api/forms/published
```

From a browser:

```text
http://YOUR_EC2_PUBLIC_IP/
```

The browser should request:

```text
http://YOUR_EC2_PUBLIC_IP/api/fields/
```

It should not request port 8000 directly.

If the API returns 502:

```bash
sudo systemctl status dynamic-forms-api
sudo journalctl -u dynamic-forms-api -n 100 --no-pager
curl http://127.0.0.1:8000/health
```

If the browser shows stale JavaScript, use DevTools with **Disable cache** and perform **Empty Cache and Hard Reload**.

## 13. Refresh Chroma capabilities

With FastAPI running:

```bash
curl -X POST http://127.0.0.1/api/spec/refresh
```

This rebuilds the local Chroma index from `app/data/angular_material_capabilities.json`.

## 14. HTTPS

For trusted HTTPS, use a domain pointing to the EC2 public IP:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d forms.example.com
```

Keep ports 80 and 443 open. Remove public port 8000 after Nginx works.

## 15. Security checklist

- Rotate any API keys or database passwords that were exposed.
- Keep `.env` out of Git.
- Keep `.pem` files out of Git.
- Use RDS security-group-to-EC2-security-group access on port 5432.
- Restrict SSH port 22 to your current IP.
- Expose only Nginx ports 80/443 in normal operation.
- Set AWS billing alerts and monitor EBS, public IPv4, RDS, and EC2 usage.

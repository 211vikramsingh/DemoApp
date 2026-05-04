# Trading Bot — User Guide
## How to Run on Any Windows 11 System

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [First-Time Setup](#2-first-time-setup)
3. [Starting the Application](#3-starting-the-application)
4. [Accessing the Dashboard](#4-accessing-the-dashboard)
5. [Stopping the Application](#5-stopping-the-application)
6. [Updating the Application](#6-updating-the-application)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

You only need **one tool** installed: **Docker Desktop**.

### Install Docker Desktop

1. Go to https://www.docker.com/products/docker-desktop/
2. Download the **Windows** installer
3. Run the installer (accepts defaults — WSL 2 backend is recommended)
4. Restart your PC when prompted
5. Open Docker Desktop and wait for it to show **"Engine running"** in the bottom-left

> **System Requirements**
> - Windows 11 (any edition)
> - 8 GB RAM minimum (16 GB recommended)
> - 20 GB free disk space
> - Internet connection (for first-time image downloads only)

### Verify Docker is working

Open **PowerShell** and run:
```powershell
docker --version
docker compose version
```
Both commands must return a version number. If either fails, reinstall Docker Desktop.

---

## 2. First-Time Setup

### Step 1 — Get the application files

If you received a ZIP:
```powershell
Expand-Archive trading-bot.zip -DestinationPath C:\trading-bot
cd C:\trading-bot\trading-bot
```

If you have the folder already (e.g., from this lab):
```powershell
cd "C:\Users\azureuser\odl-user-lab\odl-user-2208734_clabs\trading-bot"
```

### Step 2 — Configure your environment

Copy the example configuration file and edit it:
```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in the following in `.env` (minimum required — everything else is optional):

| Variable | What to enter | Example |
|---|---|---|
| `DB_PASSWORD` | A strong database password | `MyDB$ecure2024` |
| `SECRET_KEY` | Random 64-char string (see below) | *(generated)* |
| `ENCRYPTION_KEY` | Random 64-char string (see below) | *(generated)* |
| `FIRST_RUN_ADMIN_USERNAME` | Your admin login name | `admin` |
| `FIRST_RUN_ADMIN_PASSWORD` | A strong admin password | `Tr@ding$2024!` |

**Generate secure keys** (run in PowerShell):
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Run this **twice** — paste first output as `SECRET_KEY`, second as `ENCRYPTION_KEY`.

> **Optional broker keys** — only needed for live trading:
> - `KITE_API_KEY` / `KITE_API_SECRET` — from https://developers.kite.trade/
> - `DELTA_API_KEY` / `DELTA_API_SECRET` — from https://www.delta.exchange/app/account/api-keys
> - `TELEGRAM_BOT_TOKEN` — create a bot via @BotFather on Telegram

---

## 3. Starting the Application

### Easiest way — double-click the launcher

In File Explorer, navigate to the `trading-bot` folder and **double-click `start.bat`**.

The launcher will:
1. Check Docker is installed and running
2. Pull required Docker images (only on first run, ~700 MB)
3. Start all 6 services automatically
4. Print the URLs to access the app

### Manual way — PowerShell

```powershell
cd "C:\path\to\trading-bot"
docker compose up -d
```

Wait about 30–60 seconds for all services to become healthy, then check:
```powershell
docker compose ps
```

All services should show `(healthy)` or `Up`:
```
NAME                        STATUS
trading-bot-backend-1       Up (healthy)
trading-bot-celery_worker-1 Up
trading-bot-frontend-1      Up
trading-bot-nginx-1         Up (healthy)
trading-bot-postgres-1      Up (healthy)
trading-bot-redis-1         Up (healthy)
```

---

## 4. Accessing the Dashboard

Once all services are running, open your browser:

| What | URL |
|---|---|
| **Main Dashboard** | http://localhost |
| **API Documentation** (Swagger) | http://localhost/api/docs |
| **Alternative API Docs** (ReDoc) | http://localhost/api/redoc |

### Logging In

1. Go to http://localhost
2. Enter your credentials:
   - **Username**: whatever you set as `FIRST_RUN_ADMIN_USERNAME` in `.env` (default: `admin`)
   - **Password**: whatever you set as `FIRST_RUN_ADMIN_PASSWORD` in `.env` (default: `changeme_strong_password`)
3. Click **Login**

> **Important**: The login uses the **app's own user accounts**, not your Zerodha or broker login.
> Broker API keys are configured separately in `.env` or via the Admin panel after login.

---

## 5. Stopping the Application

```powershell
cd "C:\path\to\trading-bot"
docker compose down
```

This stops all containers but **preserves your data** (trades, strategies, portfolio).

To stop AND delete all data (full reset):
```powershell
docker compose down -v
```
> ⚠️ The `-v` flag deletes the database and Redis volumes — all trades and settings are lost.

---

## 6. Updating the Application

```powershell
cd "C:\path\to\trading-bot"
docker compose down
docker compose pull
docker compose build
docker compose up -d
```

Your data is preserved because the database volume is not affected by rebuilds.

---

## 7. Troubleshooting

### "Docker Desktop is not running"
Open Docker Desktop from the Start Menu and wait for the whale icon to appear in the system tray.

### Login fails with "Invalid credentials"
- Make sure you typed the username exactly as it appears in `.env` (case-sensitive)
- Default credentials: username `admin`, password `changeme_strong_password`
- If you changed `.env` after first run, the admin password in the database was already set — restart with `-v` to reset: `docker compose down -v && docker compose up -d`

### "Port 80 already in use"
Another application (IIS, another web server) is using port 80. Stop it or change the nginx port in `docker-compose.yml`:
```yaml
nginx:
  ports:
    - "8080:80"   # change 8080 to any free port
```
Then access the app at http://localhost:8080

### Backend keeps restarting
Check logs:
```powershell
docker logs trading-bot-backend-1 --tail 50
```

### Database connection errors
```powershell
docker logs trading-bot-postgres-1 --tail 20
```
Ensure `DB_USER`, `DB_PASSWORD`, `DB_NAME` in `.env` are set correctly.

### Check all service logs at once
```powershell
docker compose logs --tail 30
```

### Full restart (preserving data)
```powershell
docker compose restart
```

### View running service health
```powershell
docker compose ps
```

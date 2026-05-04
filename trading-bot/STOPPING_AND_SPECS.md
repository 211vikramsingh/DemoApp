# Stopping the Application & Hardware Requirements

---

## Table of Contents

1. [How to Stop the Application](#1-how-to-stop-the-application)
2. [Choosing the Right Stop Command](#2-choosing-the-right-stop-command)
3. [What Happens to Your Data?](#3-what-happens-to-your-data)
4. [Minimum Hardware Specifications](#4-minimum-hardware-specifications)
5. [Cloud VM Equivalents (Optional)](#5-cloud-vm-equivalents-optional)
6. [Performance Tips](#6-performance-tips)

---

## 1. How to Stop the Application

All commands must be run from the `trading-bot\` folder in PowerShell:

```powershell
cd "c:\Users\azureuser\odl-user-lab\odl-user-2208734_clabs\trading-bot"
```

---

### Option A — Pause (stop containers, keep all data)

> **Use this for**: End of day, restarting the PC, taking a break.
> Data is **fully preserved**. `docker compose up -d` brings everything back instantly.

```powershell
docker compose stop
```

To resume later:
```powershell
docker compose start
```

---

### Option B — Full shutdown (remove containers, keep all data)

> **Use this for**: Freeing RAM and CPU when you won't trade for a while.
> Containers are deleted but **database and Redis data are preserved** in Docker volumes.

```powershell
docker compose down
```

To restart fresh from this state:
```powershell
docker compose up -d
```

---

### Option C — Full wipe (remove containers AND all data)

> ⚠️ **DESTRUCTIVE — cannot be undone.**
> Use only when you want a completely clean slate (e.g. changed admin password in `.env` and need it to take effect, or resetting for a new user).

```powershell
docker compose down -v
```

> This deletes:
> - All trade history
> - All strategies
> - All user accounts (including admin)
> - All wallet balances
> - All Redis state (circuit breaker counters, kill switch flags)
>
> On next `docker compose up -d`, the admin account will be recreated from `.env`.

---

### Option D — Stop a single service

Useful for restarting just the backend or worker after a code change without touching the database.

```powershell
# Stop and restart just the backend:
docker compose restart backend

# Stop and restart just the Celery worker:
docker compose restart celery_worker

# Stop and restart nginx (e.g. after nginx.conf change):
docker compose restart nginx
```

---

### Option E — Emergency stop via Kill Switch (preferred during live trading)

If you are actively trading and want to halt all new orders **without stopping the server**:

1. Open **http://localhost** in your browser
2. Click the red **Kill Switch** button in the header
3. Confirm the prompt

This:
- Stops all strategy workers from placing new orders
- Closes any open positions (if configured)
- Keeps the application running so you can monitor positions
- Does **not** stop Docker containers

To re-enable trading after resolving the issue:
- Go to http://localhost → Dashboard → Kill Switch → **Reset Kill Switch**

---

### Quick Reference Table

| Scenario | Command | Keeps Data? | Keeps Containers? |
|---|---|---|---|
| Taking a break (end of day) | `docker compose stop` | ✅ Yes | ✅ Yes (stopped) |
| Freeing up RAM/CPU | `docker compose down` | ✅ Yes | ❌ No |
| Completely reset everything | `docker compose down -v` | ❌ No | ❌ No |
| Restart one service | `docker compose restart <name>` | ✅ Yes | ✅ Yes |
| Halt trading only (no downtime) | Kill Switch in browser | ✅ Yes | ✅ Yes |

---

## 2. Choosing the Right Stop Command

```
Are you actively in a live trade right now?
│
├── YES → Use Kill Switch first (browser) → wait for positions to close → then stop
│
└── NO
    │
    ├── Stopping for < 8 hours (lunch break, overnight)?
    │       → docker compose stop    (fastest resume)
    │
    ├── Stopping for > 8 hours / days (not trading for a while)?
    │       → docker compose down    (frees all RAM and CPU)
    │
    └── Changed admin password / DB password / encryption key in .env?
            → docker compose down -v  (WARNING: deletes all data)
```

---

## 3. What Happens to Your Data?

### Docker Volumes (where data lives)

```
postgres_data   ← All trades, strategies, users, wallets, audit logs
redis_data      ← Circuit breaker state, kill switch flags, Celery queue state
```

| Action | postgres_data | redis_data | Code files |
|---|---|---|---|
| `docker compose stop` | ✅ Safe | ✅ Safe | ✅ Safe |
| `docker compose start` | ✅ Restored | ✅ Restored | ✅ Unchanged |
| `docker compose down` | ✅ Safe | ✅ Safe | ✅ Safe |
| `docker compose up -d` | ✅ Restored | ✅ Restored | ✅ Unchanged |
| `docker compose down -v` | ❌ **DELETED** | ❌ **DELETED** | ✅ Safe |
| Deleting `trading-bot/` folder | ❌ **DELETED** | ❌ **DELETED** | ❌ **DELETED** |

### How to back up your database before stopping

```powershell
# While containers are running, export the database:
docker exec trading-bot-postgres-1 pg_dump -U tradingbot tradingbot > backup_$(Get-Date -Format "yyyyMMdd_HHmm").sql

# To restore from backup:
docker exec -i trading-bot-postgres-1 psql -U tradingbot tradingbot < backup_20260504_0900.sql
```

---

## 4. Minimum Hardware Specifications

### 4.1 — Single User (1 active trader, paper or live)

This is the minimum configuration to run the full stack comfortably:

| Component | Minimum | Recommended |
|---|---|---|
| **CPU** | 4-core (Intel i5-10th gen / AMD Ryzen 5 3600) | 6-core (i5-12th gen / Ryzen 5 5600) |
| **RAM** | **8 GB** | **16 GB** |
| **Storage** | 30 GB free SSD (SATA is fine) | 50 GB NVMe SSD |
| **OS** | Windows 10 64-bit (build 19041+) | Windows 11 64-bit |
| **Internet** | 10 Mbps broadband | 25 Mbps (for live market data) |
| **Docker Desktop** | v4.0+ | Latest |

#### Memory breakdown (1 user, paper trading):

| Service | Typical RAM |
|---|---|
| nginx | ~30 MB |
| frontend (Node) | ~200 MB |
| backend (FastAPI) | ~150 MB |
| celery_worker | ~200 MB |
| PostgreSQL + TimescaleDB | ~300 MB |
| Redis | ~30 MB |
| Windows + Docker Desktop overhead | ~2–3 GB |
| **Total** | **~3.5–4 GB active** |

> An 8 GB laptop will work but will feel slow if you also have a browser and VS Code open simultaneously. **16 GB is strongly recommended for a comfortable experience.**

#### CPU requirements (1 user):

| Workload | CPU demand |
|---|---|
| Idle (monitoring only) | < 5% |
| Running 1 automated strategy | 10–20% |
| Running 5 automated strategies | 25–40% |
| Running backtests | 60–80% (spikes, then drops) |
| Options chain with Greeks refresh | 10–15% |

---

### 4.2 — Five Simultaneous Users (5 traders, mixed strategies)

For 5 users each running strategies concurrently, the resource demands scale significantly due to:
- 5 independent strategy polling loops in the Celery worker
- 5 concurrent WebSocket connections to the backend
- More frequent database writes (trades, signals, audit logs)
- More broker API calls (if live trading)

| Component | Minimum | Recommended |
|---|---|---|
| **CPU** | 8-core (Intel i7-12th gen / AMD Ryzen 7 5700) | 12-core (i9-12th gen / Ryzen 9 5900X) |
| **RAM** | **16 GB** | **32 GB** |
| **Storage** | 60 GB free NVMe SSD | 100 GB NVMe SSD (trade data grows fast) |
| **OS** | Windows 11 64-bit | Windows 11 64-bit or Ubuntu Server 22.04 |
| **Internet** | 50 Mbps broadband | 100 Mbps (separate line for the bot is ideal) |
| **Docker Desktop** | v4.25+ | Latest, with WSL 2 backend |
| **Network latency** | < 50 ms to NSE/Delta servers | < 20 ms (co-location preferred for live) |

#### Memory breakdown (5 users, all running strategies):

| Service | Typical RAM |
|---|---|
| nginx | ~30 MB |
| frontend (Node) | ~250 MB |
| backend (FastAPI, 5 concurrent users) | ~400–600 MB |
| celery_worker (5 concurrent strategies) | ~600–900 MB |
| PostgreSQL + TimescaleDB (more writes) | ~600–1000 MB |
| Redis (5x circuit breaker state) | ~50 MB |
| Windows + Docker Desktop overhead | ~3–4 GB |
| **Total** | **~8–10 GB active** |

> **16 GB is the hard minimum** for 5 users. At peak (all users running backtests simultaneously), RAM usage can spike to 12–14 GB. **32 GB gives comfortable headroom.**

#### Scaling the Celery worker for 5 users

By default, the Celery worker runs with 4 concurrent processes (`-c 4`). For 5 active users each running multiple strategies, increase this in `docker-compose.yml`:

```yaml
# docker-compose.yml → celery_worker → command
command: celery -A app.workers.celery_app worker --loglevel=info -Q kill_queue,default -c 8
```

Also scale the backend with multiple Uvicorn workers:

```yaml
# docker-compose.yml → backend → command
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

> Note: Remove `--reload` when using multiple workers — it only works with a single worker process.

---

### 4.3 — Spec Summary at a Glance

```
┌───────────────────────────────────────────────────────────────────┐
│                   HARDWARE SPEC SUMMARY                          │
├──────────────┬────────────────────────┬──────────────────────────┤
│              │     1 USER             │     5 USERS              │
├──────────────┼────────────────────────┼──────────────────────────┤
│ CPU (min)    │ 4-core / 2.5 GHz       │ 8-core / 3.0 GHz         │
│ CPU (rec.)   │ 6-core / 3.5 GHz       │ 12-core / 3.8 GHz        │
│ RAM (min)    │ 8 GB                   │ 16 GB                    │
│ RAM (rec.)   │ 16 GB                  │ 32 GB                    │
│ Storage (min)│ 30 GB SSD              │ 60 GB NVMe SSD           │
│ Storage (rec)│ 50 GB NVMe SSD         │ 100 GB NVMe SSD          │
│ Internet     │ 10 Mbps                │ 50 Mbps                  │
│ OS           │ Windows 10/11 64-bit   │ Windows 11 / Ubuntu 22   │
├──────────────┼────────────────────────┼──────────────────────────┤
│ Example      │ Dell Inspiron 15       │ Dell XPS 15 (i9)         │
│ Laptops      │ Lenovo IdeaPad 5       │ ASUS ProArt Studiobook   │
│              │ HP Pavilion 14         │ ThinkPad X1 Extreme       │
└──────────────┴────────────────────────┴──────────────────────────┘
```

---

## 5. Cloud VM Equivalents (Optional)

If you don't want to run this on a laptop (for better uptime and lower latency):

### For 1 User

| Cloud | VM Type | vCPU | RAM | Cost (est.) |
|---|---|---|---|---|
| AWS | `t3.medium` | 2 vCPU | 4 GB | ~$30/month |
| AWS | `t3.large` *(recommended)* | 2 vCPU | 8 GB | ~$60/month |
| Azure | `B2s` | 2 vCPU | 4 GB | ~$35/month |
| Azure | `B2ms` *(recommended)* | 2 vCPU | 8 GB | ~$70/month |
| GCP | `e2-medium` | 2 vCPU | 4 GB | ~$25/month |

### For 5 Users

| Cloud | VM Type | vCPU | RAM | Cost (est.) |
|---|---|---|---|---|
| AWS | `t3.xlarge` | 4 vCPU | 16 GB | ~$120/month |
| AWS | `m5.xlarge` *(recommended)* | 4 vCPU | 16 GB | ~$140/month |
| Azure | `D4s_v3` | 4 vCPU | 16 GB | ~$145/month |
| GCP | `n2-standard-4` | 4 vCPU | 16 GB | ~$130/month |

> Cloud VMs give you better uptime (no laptop sleep/shutdown), lower latency to Indian exchanges, and easy backups. Use Mumbai region (`ap-south-1` on AWS, `centralindia` on Azure) for lowest NSE latency.

---

## 6. Performance Tips

### Reduce resource usage

```powershell
# Check how much RAM each container is using right now:
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### If RAM is tight (8 GB laptop)

1. **Disable `--reload` on the backend** — hot-reload watches the filesystem and uses extra memory:
   ```yaml
   # docker-compose.yml → backend → command
   command: uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Reduce PostgreSQL shared_buffers** — add to `docker-compose.yml` under postgres:
   ```yaml
   command: postgres -c shared_buffers=128MB -c max_connections=50
   ```

3. **Reduce Celery concurrency** — change `-c 4` to `-c 2`:
   ```yaml
   command: celery -A app.workers.celery_app worker --loglevel=info -Q kill_queue,default -c 2
   ```

4. **Close other applications** — Chrome, VS Code, and Teams each use 500 MB–2 GB.

### If the app is slow to start

Docker Desktop takes 30–60 seconds to fully initialise on first launch. Wait for all services to show **healthy**:

```powershell
docker compose ps
```

All services should show `Up (healthy)` before you try to log in. The backend health check can take up to 120 seconds on first run (database table creation + admin seeding).

### Storage growth

Trade data grows over time. Check disk usage:

```powershell
# Total Docker disk usage:
docker system df

# Just the postgres volume:
docker exec trading-bot-postgres-1 psql -U tradingbot -c "SELECT pg_size_pretty(pg_database_size('tradingbot'));"
```

To clean up unused Docker images and build cache (safe to run anytime):

```powershell
docker system prune -f
```

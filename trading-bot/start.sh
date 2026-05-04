#!/usr/bin/env bash
# Trading Bot — Portable Launcher
# Checks Docker is installed, then brings up the full stack.
set -e

BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BOLD}=== Trading Bot Launcher ===${NC}"

# ── 1. Check Docker ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "${RED}[ERROR] Docker is not installed.${NC}"
  echo "Install Docker Desktop from: https://docs.docker.com/get-docker/"
  exit 1
fi

# ── 2. Check Docker Compose v2 ───────────────────────────────────────────────
if ! docker compose version &>/dev/null; then
  echo -e "${RED}[ERROR] Docker Compose v2 is not available.${NC}"
  echo "Upgrade Docker Desktop or install the Compose plugin:"
  echo "  https://docs.docker.com/compose/install/"
  exit 1
fi

echo -e "${GREEN}[OK] Docker $(docker --version | awk '{print $3}' | tr -d ',')${NC}"
echo -e "${GREEN}[OK] Docker Compose $(docker compose version --short)${NC}"

# ── 3. First-run wizard ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}[SETUP] .env not found — running first-run wizard...${NC}"

  read -rp "Zerodha Kite API Key      : " KITE_API_KEY
  read -rsp "Zerodha Kite API Secret   : " KITE_API_SECRET; echo
  read -rp "Delta Exchange API Key    : " DELTA_API_KEY
  read -rsp "Delta Exchange API Secret : " DELTA_API_SECRET; echo
  read -rp "Admin username            : " ADMIN_USERNAME
  read -rsp "Admin password            : " ADMIN_PASSWORD; echo
  read -rp "Telegram Bot Token (optional, press Enter to skip): " TELEGRAM_TOKEN

  # Generate a strong random secret key
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
  ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

  cat > .env <<EOF
# ── Database ──────────────────────────────────────────────────────────────────
DB_USER=tradingbot
DB_PASSWORD=tradingbot
DB_NAME=tradingbot

# ── Application ───────────────────────────────────────────────────────────────
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
DEBUG=false

# ── Zerodha Kite Connect ──────────────────────────────────────────────────────
KITE_API_KEY=${KITE_API_KEY}
KITE_API_SECRET=${KITE_API_SECRET}

# ── Delta Exchange ────────────────────────────────────────────────────────────
DELTA_API_KEY=${DELTA_API_KEY}
DELTA_API_SECRET=${DELTA_API_SECRET}

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}

# ── Admin ─────────────────────────────────────────────────────────────────────
FIRST_RUN_ADMIN_USERNAME=${ADMIN_USERNAME}
FIRST_RUN_ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
  echo -e "${GREEN}[OK] .env created with encrypted credentials.${NC}"
fi

# ── 4. Pull latest images & start stack ──────────────────────────────────────
echo -e "${BOLD}[INFO] Pulling latest images...${NC}"
docker compose pull

echo -e "${BOLD}[INFO] Starting all services...${NC}"
docker compose up -d --wait

echo ""
echo -e "${GREEN}${BOLD}=== Trading Bot is running ===${NC}"
echo -e "  Dashboard : ${BOLD}http://localhost${NC}"
echo -e "  API Docs  : ${BOLD}http://localhost/api/docs${NC}"
echo -e "  API       : ${BOLD}http://localhost:8000${NC}"
echo ""
echo -e "Stop the bot : ${YELLOW}docker compose down${NC}"

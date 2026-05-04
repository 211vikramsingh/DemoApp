@echo off
REM Trading Bot — Portable Launcher (Windows)
REM Checks Docker is installed, then brings up the full stack.
setlocal EnableDelayedExpansion

echo === Trading Bot Launcher ===

REM ── 1. Check Docker ──────────────────────────────────────────────────────────
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker is not installed.
    echo Install Docker Desktop from: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM ── 2. Check Docker Compose v2 ───────────────────────────────────────────────
docker compose version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker Compose v2 is not available.
    echo Upgrade Docker Desktop or visit: https://docs.docker.com/compose/install/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('docker --version') do echo [OK] %%i
for /f "tokens=*" %%i in ('docker compose version') do echo [OK] %%i

REM ── 3. First-run wizard ───────────────────────────────────────────────────────
if not exist ".env" (
    echo [SETUP] .env not found — running first-run wizard...

    set /p KITE_API_KEY="Zerodha Kite API Key      : "
    set /p KITE_API_SECRET="Zerodha Kite API Secret   : "
    set /p DELTA_API_KEY="Delta Exchange API Key    : "
    set /p DELTA_API_SECRET="Delta Exchange API Secret : "
    set /p ADMIN_USERNAME="Admin username            : "
    set /p ADMIN_PASSWORD="Admin password            : "
    set /p TELEGRAM_TOKEN="Telegram Bot Token (optional, press Enter to skip): "

    REM Generate random keys using PowerShell
    for /f %%i in ('powershell -command "[System.Web.Security.Membership]::GeneratePassword(64,0)"') do set SECRET_KEY=%%i
    for /f %%i in ('powershell -command "[System.Web.Security.Membership]::GeneratePassword(64,0)"') do set ENCRYPTION_KEY=%%i

    (
        echo # ── Database ──────────────────────────────────────────────────────────────────
        echo DB_USER=tradingbot
        echo DB_PASSWORD=tradingbot
        echo DB_NAME=tradingbot
        echo.
        echo # ── Application ───────────────────────────────────────────────────────────────
        echo SECRET_KEY=!SECRET_KEY!
        echo ENCRYPTION_KEY=!ENCRYPTION_KEY!
        echo DEBUG=false
        echo.
        echo # ── Zerodha Kite Connect ──────────────────────────────────────────────────────
        echo KITE_API_KEY=!KITE_API_KEY!
        echo KITE_API_SECRET=!KITE_API_SECRET!
        echo.
        echo # ── Delta Exchange ────────────────────────────────────────────────────────────
        echo DELTA_API_KEY=!DELTA_API_KEY!
        echo DELTA_API_SECRET=!DELTA_API_SECRET!
        echo.
        echo # ── Telegram ──────────────────────────────────────────────────────────────────
        echo TELEGRAM_BOT_TOKEN=!TELEGRAM_TOKEN!
        echo.
        echo # ── Admin ─────────────────────────────────────────────────────────────────────
        echo FIRST_RUN_ADMIN_USERNAME=!ADMIN_USERNAME!
        echo FIRST_RUN_ADMIN_PASSWORD=!ADMIN_PASSWORD!
    ) > .env
    echo [OK] .env created.
)

REM ── 4. Pull latest images & start stack ──────────────────────────────────────
echo [INFO] Pulling latest images...
docker compose pull

echo [INFO] Starting all services...
docker compose up -d --wait

echo.
echo === Trading Bot is running ===
echo   Dashboard : http://localhost
echo   API Docs  : http://localhost/api/docs
echo   API       : http://localhost:8000
echo.
echo Stop the bot : docker compose down
pause

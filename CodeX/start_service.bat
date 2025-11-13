@echo off
cd /d C:\Brototype\CodeXLearning\Backend\CodeX

echo ===========================================
echo Starting CodeX Backend with Stripe Webhook
echo ===========================================
echo.

:: Activate virtual environment
call ..\venv\Scripts\activate

:: Check if Stripe CLI is installed
where stripe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Stripe CLI is not installed!
    echo Please install it first:
    echo   winget install stripe.stripe-cli
    echo   OR download from: https://github.com/stripe/stripe-cli/releases
    echo.
    pause
    exit /b 1
)

:: Start Daphne server in a new window
echo [1/3] Starting Daphne server...
start "Django Server" cmd /k "call ..\venv\Scripts\activate && daphne -b 0.0.0.0 -p 8000 CodeX.asgi:application"

:: Wait a bit for server to start
timeout /t 3 /nobreak >nul

:: Start Celery worker in a new window
echo [2/3] Starting Celery worker...
start "Celery Worker" cmd /k "call ..\venv\Scripts\activate && celery -A CodeX worker --loglevel=info --pool=solo"

:: Wait a bit
timeout /t 2 /nobreak >nul

:: Start Stripe webhook listener in a new window
echo [3/3] Starting Stripe webhook listener...
echo.
echo IMPORTANT: Copy the webhook secret shown below and add it to your .env file:
echo   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
echo.
start "Stripe Webhook" cmd /k "stripe listen --forward-to http://localhost:8000/webhooks/stripe/"

echo.
echo ===========================================
echo All services started in separate windows:
echo - Django Server (Daphne)
echo - Celery Worker
echo - Stripe Webhook Listener
echo.
echo NOTE: For production, configure webhook in Stripe Dashboard instead!
echo ===========================================
echo.
pause


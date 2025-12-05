@echo off
echo ================================================
echo  TRANSLATOR API - LOCAL TEST SETUP
echo ================================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running! Please start Docker Desktop first.
    pause
    exit /b 1
)

echo [1/4] Generating secure JWT secret...
for /f %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set JWT_SECRET=%%i

echo [2/4] Creating .env file...
(
echo JWT_SECRET_KEY=%JWT_SECRET%
echo GRAFANA_PASSWORD=admin123
echo ALLOWED_ORIGINS=http://localhost:3000
echo ENVIRONMENT=production
echo LOG_LEVEL=INFO
echo REDIS_URL=redis://redis:6379/0
) > .env

echo [3/4] Building and starting services...
docker-compose -f docker-compose.prod.yml up --build -d

echo [4/4] Waiting for services to start...
timeout /t 30 /nobreak >nul

echo.
echo ================================================
echo  SERVICES STARTED!
echo ================================================
echo.
echo   API:        http://localhost:8000
echo   Health:     http://localhost:8000/health
echo   Metrics:    http://localhost:8000/metrics
echo   Prometheus: http://localhost:9090
echo   Grafana:    http://localhost:3001 (admin/admin123)
echo.
echo ================================================
echo  QUICK TEST COMMANDS:
echo ================================================
echo.
echo   # Check health
echo   curl http://localhost:8000/health
echo.
echo   # View metrics
echo   curl http://localhost:8000/metrics
echo.
echo   # Create API key
echo   curl -X POST "http://localhost:8000/dev/create-api-key?tier=pro"
echo.
echo   # View logs
echo   docker-compose -f docker-compose.prod.yml logs -f translator-api
echo.
pause

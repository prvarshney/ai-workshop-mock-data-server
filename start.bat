@echo off
REM Start the whole workshop app on Windows.
REM
REM     start.bat
REM
REM Settings live in a .env file next to this script. The first run creates one
REM with a freshly generated signing secret; open it and change the password.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

if not exist ".env" (
    echo No .env yet - creating one with a fresh JWT_SECRET.
    for /f %%i in ('%PY% -c "import secrets; print(secrets.token_hex(32))"') do set "SECRET=%%i"
    (
        echo # Settings for the workshop app. This file is not committed to git.
        echo.
        echo # Pulse instructor password. CHANGE THIS before the workshop.
        echo ADMIN_PASSWORD=cu2026
        echo.
        echo # Signs the instructor login. Keep it, so restarts do not log you out.
        echo JWT_SECRET=%SECRET%
        echo.
        echo JWT_HOURS=12
        echo PORT=8000
        echo REDIS_URL=redis://localhost:6379/0
    ) > .env
    echo Created .env - open it and change ADMIN_PASSWORD.
    echo.
)

REM Load every name=value line from .env into the environment.
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if not "%%a"=="" set "%%a=%%b"
)

%PY% -c "import fastapi, uvicorn, redis, qrcode, jwt" 2>nul
if errorlevel 1 (
    echo Some Python packages are missing. Install them with:
    echo     %PY% -m pip install -r requirements.txt
    exit /b 1
)

%PY% main.py

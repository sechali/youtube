@echo off
cd /d "%~dp0"
title Media Downloader Server

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Environment belum disetup. Menjalankan Setup_Install.bat...
    call "%~dp0Setup_Install.bat"
    if not exist ".venv\Scripts\python.exe" (
        exit /b 1
    )
)

echo ============================================
echo   MENJALANKAN MEDIA DOWNLOADER...
echo   Browser akan terbuka otomatis.
echo   Tutup jendela ini untuk mematikan server.
echo ============================================
echo.

REM Buka browser setelah jeda singkat agar server siap
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

if errorlevel 1 (
    echo.
    echo [ERROR] Server berhenti dengan error.
    pause
)

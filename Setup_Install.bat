@echo off
cd /d "%~dp0"
title Setup Media Downloader

echo ============================================
echo   SETUP MEDIA DOWNLOADER (PYTHON WEB APP)
echo ============================================
echo.

REM 1. Cek Python
set "PY_CMD="
python --version >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=python"
) else (
    py -3 --version >nul 2>&1
    if %errorlevel%==0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python belum terinstal di komputer ini!
    echo Silakan download dan install Python 3.10+ dari: https://www.python.org/downloads/
    echo PENTING: Centang "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

echo [OK] Python ditemukan:
%PY_CMD% --version
echo.

REM 2. Buat virtual environment (.venv) jika belum ada
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Membuat virtual environment ^(.venv^)...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [OK] Virtual environment ^(.venv^) sudah ada.
)
echo.

REM 3. Install library dari requirements.txt
echo [INFO] Menginstall library Python ^(fastapi, uvicorn, yt-dlp^)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Gagal menginstall library dari requirements.txt.
    echo Pastikan koneksi internet aktif.
    pause
    exit /b 1
)
echo [OK] Semua library Python berhasil diinstall.
echo.

REM 4. Cek FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel%==0 (
    echo [OK] FFmpeg sudah terinstal.
) else (
    echo [INFO] FFmpeg belum ditemukan di PATH. Mencoba install via winget...
    winget --version >nul 2>&1
    if %errorlevel%==0 (
        winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
        if errorlevel 1 (
            echo [PERINGATAN] Instalasi FFmpeg via winget gagal.
            echo Silakan install FFmpeg secara manual agar penggabungan video HD ^& konversi MP3 berjalan.
        ) else (
            echo [OK] FFmpeg berhasil diinstall. Tutup dan buka ulang terminal jika belum terbaca.
        )
    ) else (
        echo [PERINGATAN] winget tidak tersedia.
        echo Silakan install FFmpeg secara manual dari https://www.gyan.dev/ffmpeg/builds/
        echo dan tambahkan folder bin FFmpeg ke Environment Variables PATH.
    )
)

echo.
echo ============================================
echo   SETUP SELESAI!
echo   Klik 2x "Jalankan_Aplikasi.bat" untuk mulai.
echo ============================================
pause

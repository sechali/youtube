# Media Downloader Web App

Aplikasi web berbasis Python (FastAPI + `yt-dlp` + `FFmpeg` + SQLite) untuk mengunduh video dan mengekstrak audio MP3 dari berbagai situs seperti YouTube, Facebook, Instagram, Threads, TikTok, dan lainnya.

## Panduan untuk Developer (Melanjutkan Pengembangan di Komputer Baru)

### Prasyarat
1. **Python 3.10+** (pastikan centang *Add python.exe to PATH* saat instalasi).
2. **Git** (opsional, jika menggunakan repository GitHub/GitLab).
3. **VS Code** atau IDE favorit Anda.

### Setup Environment Development
1. Buka folder project di terminal:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *(Atau cukup klik 2x file `Setup_Install.bat`)*

2. Jalankan server dalam mode **Hot-Reload / Dev Mode**:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *Dengan flag `--reload`, setiap kali Anda mengedit file di folder `app/`, server akan otomatis me-restart tanpa perlu dimatikan manual.*

### Struktur File Penting:
- `app/main.py`: Endpoint API FastAPI (inspeksi link, trigger download, task management, folder setting).
- `app/downloader.py`: Logika yt-dlp, thread worker background, progress tracking, dan cancel/resume logic.
- `app/database.py`: Skema SQLite untuk riwayat unduhan & setting folder/cookies.
- `app/static/`: Frontend web (UI, styling responsif, dan logika JavaScript interaktif).


## Cara Menjalankan

### Cara Cepat (1x Klik di Windows)
1. **Saat pertama kali / pindah komputer**: klik 2x [Setup_Install.bat](Setup_Install.bat) untuk membuat `.venv`, menginstall semua library (`fastapi`, `uvicorn`, `yt-dlp`), dan mengecek `FFmpeg`.
2. **Menjalankan aplikasi**: klik 2x [Jalankan_Aplikasi.bat](Jalankan_Aplikasi.bat) — server akan menyala dan browser otomatis terbuka ke `http://127.0.0.1:8000`.

### Cara Manual (Terminal)
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Lalu buka browser ke: `http://127.0.0.1:8000`

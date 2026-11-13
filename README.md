# Media Downloader Pro — Video & Audio HD

Aplikasi web modern berbasis Python (**FastAPI** + **yt-dlp** + **FFmpeg** + **SQLite**) untuk mengunduh video kualitas tinggi hingga 4K, mengekstrak audio berbagai format (MP3, M4A, FLAC, WAV, AAC, OPUS), batch download multi-link, unduh subtitle/caption, dan manajemen antrian unduhan secara otomatis.

Mendukung berbagai platform populer: **YouTube, TikTok, Instagram (Reels & Post), Facebook, Twitter / X, Threads, Vimeo**, dan ribuan situs web lainnya yang didukung oleh engine `yt-dlp`.

---

## ✨ Fitur-Fitur Utama

### 1. Unduhan Fleksibel (Single & Batch Download)
- **Single Link**: Inspeksi URL seketika, preview thumbnail visual, durasi, uploader, dan deteksi subtitle.
- **Batch / Multi-Link**: Masukkan puluhan link sekaligus (satu link per baris) dan unduh secara serentak dengan satu klik.
- **Dukungan Playlist**: Deteksi playlist otomatis dengan pemilih item individual (misal: 1-5, 8, 10) atau unduh seluruh playlist ke dalam arsip `.zip`.

### 2. Kualitas & Format Lengkap
- **Video Kualitas Tinggi**: Pilihan resolusi otomatis sesuai video asli: **Best, 4K (2160p), 2K (1440p), 1080p (Full HD), 720p (HD), 480p, 360p**.
- **Format Kontainer Video**: **MP4** (universal), **MKV** (multi-track), dan **WebM**.
- **Format Ekstraksi Audio**: **MP3, M4A, FLAC (Lossless), WAV, AAC, OPUS**.
- **Bitrate Audio**: **320 kbps (High Quality), 256 kbps, 192 kbps (Standar CD), 128 kbps**.
- **Subtitle / Caption**: Unduh subtitle (.srt/.vtt) multibahasa (Indonesia, Inggris, atau semua) serta opsi embed langsung ke video.

### 3. Queue & Concurrency Management
- Sistem antrian dengan batasan concurrency (default 3 unduhan paralel) untuk mencegah jaringan macet atau CPU overload.
- Kontrol penuh: Pantau kecepatan (MB/s), estimasi waktu selesai (ETA), tombol **Stop / Pause**, dan **Resume**.

### 4. UI / UX Modern & Interaktif
- **Dark Mode & Light Mode**: Desain responsif dengan toggle tema yang tersimpan otomatis di browser.
- **Tab Navigasi Terstruktur**: Single Link, Batch Downloader, Antrian Aktif, Riwayat Unduhan, serta Pengaturan & Info Sistem.
- **Diagnostik Sistem Real-time**: Indikator status FFmpeg, versi engine `yt-dlp`, dan sisa kapasitas ruang penyimpanan harddisk.
- **Integrasi Windows Explorer**: Tombol 1-klik untuk langsung membuka folder penyimpanan atau menandai file yang selesai diunduh di File Explorer.

### 5. Penanganan Autentikasi / Anti-Bot
- Ekstraksi cookies otomatis dari browser lokal (**Google Chrome, Microsoft Edge, Mozilla Firefox, Brave, Opera, Vivaldi**) atau menggunakan file `cookies.txt` untuk mengakses video yang membutuhkan verifikasi login, batasan usia (Age Restriction), atau konten privat.

---

## 🛠️ Prasyarat
1. **Python 3.10+** (Pastikan opsi *"Add python.exe to PATH"* dicentang saat instalasi).
2. **FFmpeg** (Otomatis dicek dan diinstall via `winget` saat setup).

---

## 🚀 Cara Menjalankan

### Cara Cepat (1x Klik di Windows)
1. **Setup Awal**: Klik 2x file [Setup_Install.bat](Setup_Install.bat). Script ini akan otomatis membuat virtual environment (`.venv`), menginstal semua dependensi, serta memastikan `FFmpeg` terpasang.
2. **Menjalankan Aplikasi**: Klik 2x file [Jalankan_Aplikasi.bat](Jalankan_Aplikasi.bat). Server FastAPI akan menyala dan browser otomatis terbuka ke:
   ```
   http://127.0.0.1:8000
   ```

### Cara Manual (Terminal / VS Code)
```powershell
# 1. Masuk ke virtual environment
.\.venv\Scripts\activate

# 2. Jalankan server dengan Hot-Reload (Dev Mode)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 📂 Struktur Proyek
```
ytdownloader/
│
├── app/
│   ├── __init__.py
│   ├── main.py          # Routing API FastAPI (Inspect, Download, Batch, Settings, Stats)
│   ├── downloader.py    # Engine yt-dlp, thread worker, concurrency semaphore, progress hooks
│   ├── database.py      # SQLite database helper, skema riwayat, migrasi, & kalkulasi statistik
│   └── static/
│       ├── index.html   # Tampilan Web Pro (Single, Batch, Queue, History, Settings)
│       ├── style.css    # Styling modern responsif, Dark/Light theme, glassmorphism
│       └── app.js       # Logika interaktif frontend, polling antrian, filter riwayat, toast
│
├── history.db           # Database SQLite lokal (riwayat unduhan & preferensi)
├── downloads/           # Folder penyimpanan unduhan default
├── Setup_Install.bat    # Script otomatisasi instalasi dep & FFmpeg
├── Jalankan_Aplikasi.bat# Script peluncur aplikasi 1-klik
├── requirements.txt     # Dependensi library Python
└── README.md
```

---

## 📜 Lisensi
MIT License — Bebas digunakan, dimodifikasi, dan dikembangkan lebih lanjut.

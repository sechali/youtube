"""
Android Launcher Script for Chaquopy
Menjalankan FastAPI secara mandiri di dalam sistem operasi Android
"""
import os
import sys
import uvicorn

def start_server(internal_dir: str, public_download_dir: str, ffmpeg_path: str = ""):
    # Set environment variables agar SQLite, folder download, dan FFmpeg binary terbaca
    os.environ["ANDROID_INTERNAL_DIR"] = internal_dir
    os.environ["ANDROID_DOWNLOAD_DIR"] = public_download_dir
    if ffmpeg_path and os.path.isfile(ffmpeg_path):
        os.environ["ANDROID_FFMPEG_PATH"] = ffmpeg_path
        # Masukkan juga direktori folder bin ke dalam PATH
        bin_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
    
    # Pastikan SSL Certificate Authority bundle (certifi) terpasang di Android sandbox
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    except Exception:
        pass

    # Pastikan sys.path mencakup root folder python
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    from app.main import app
    
    # Jalankan Uvicorn pada 127.0.0.1:8000
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    
    # Jalankan server
    server.run()

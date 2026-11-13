"""
Android Launcher Script for Chaquopy
Menjalankan FastAPI secara mandiri di dalam sistem operasi Android
"""
import os
import sys
import threading
import uvicorn

def start_server(internal_dir: str, public_download_dir: str):
    # Set environment variables agar SQLite dan folder download mengarah ke storage Android
    os.environ["ANDROID_INTERNAL_DIR"] = internal_dir
    os.environ["ANDROID_DOWNLOAD_DIR"] = public_download_dir
    
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
        log_level="info",
        access_log=False
    )
    server = uvicorn.Server(config)
    
    # Jalankan server
    server.run()

"""yt-dlp wrapper, queue concurrency manager, and background task engine."""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from app import database, logger

# Lokasi folder download: gunakan public Download Android jika tersedia
_android_download = os.environ.get("ANDROID_DOWNLOAD_DIR")
if _android_download:
    DOWNLOADS_DIR = Path(_android_download) / "YTDownloader"
else:
    DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

_TASKS_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}

# Maksimum unduhan aktif bersamaan (concurrency limiter)
MAX_CONCURRENT_DOWNLOADS = 3
_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)


def _ensure_ffmpeg_path() -> None:
    """Ensure ffmpeg is in system PATH for the current process."""
    # 1. Periksa apakah path FFmpeg Android sudah diatur via environment variable
    android_ffmpeg = os.environ.get("ANDROID_FFMPEG_PATH")
    if android_ffmpeg and os.path.isfile(android_ffmpeg):
        ffmpeg_dir = str(Path(android_ffmpeg).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{ffmpeg_dir}:{os.environ.get('PATH', '')}"
        return

    if shutil.which("ffmpeg"):
        return
    # Periksa lokasi standar winget jika belum masuk ke current os.environ["PATH"]
    winget_links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if (winget_links / "ffmpeg.exe").is_file():
        os.environ["PATH"] = f"{winget_links};{os.environ.get('PATH', '')}"


_ensure_ffmpeg_path()


def get_download_dir() -> Path:
    # 1. Jika berjalan di Android, utamakan folder publik Download HP (/storage/emulated/0/Download/YTDownloader)
    android_download = os.environ.get("ANDROID_DOWNLOAD_DIR")
    if android_download:
        p = Path(android_download)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            pass

    saved = database.get_setting("download_dir")
    if saved:
        p = Path(saved)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            pass
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOADS_DIR


def set_download_dir(path_str: str) -> Path:
    p = Path(path_str.strip()).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    database.set_setting("download_dir", str(p))
    return p


def pick_folder_dialog() -> str | None:
    """Open a native folder picker dialog via a short-lived Python subprocess (Desktop) or return download dir."""
    if os.environ.get("ANDROID_INTERNAL_DIR") or os.environ.get("ANDROID_DOWNLOAD_DIR"):
        # Di Android, lokasi download dikunci ke folder publik /storage/emulated/0/Download/YTDownloader
        return str(get_download_dir())

    current = str(get_download_dir())
    script = (
        "import sys, tkinter as tk; from tkinter import filedialog; "
        "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); "
        "folder = filedialog.askdirectory(initialdir=sys.argv[1], title='Pilih Folder Penyimpanan'); "
        "root.destroy(); print(folder or '')"
    )
    res = subprocess.run(
        [sys.executable, "-c", script, current],
        capture_output=True,
        text=True,
        timeout=120,
    )
    chosen = (res.stdout or "").strip()
    if chosen:
        return str(set_download_dir(chosen))
    return None


SUPPORTED_COOKIE_BROWSERS = {"chrome", "edge", "firefox", "brave", "opera", "vivaldi"}


def get_cookie_settings() -> dict[str, str]:
    return {
        "cookie_mode": database.get_setting("cookie_mode", "none") or "none",
        "cookie_browser": database.get_setting("cookie_browser", "chrome") or "chrome",
        "cookie_file": database.get_setting("cookie_file", "") or "",
    }


def set_cookie_settings(
    cookie_mode: str = "none",
    cookie_browser: str = "chrome",
    cookie_file: str = "",
) -> dict[str, str]:
    mode = cookie_mode if cookie_mode in ("none", "browser", "file") else "none"
    browser = cookie_browser if cookie_browser in SUPPORTED_COOKIE_BROWSERS else "chrome"
    cfile = cookie_file.strip()
    database.set_setting("cookie_mode", mode)
    database.set_setting("cookie_browser", browser)
    database.set_setting("cookie_file", cfile)
    return get_cookie_settings()


def pick_cookies_file_dialog() -> str | None:
    """Open a native file picker dialog to select a Netscape cookies.txt file."""
    current = str(get_download_dir())
    script = (
        "import sys, tkinter as tk; from tkinter import filedialog; "
        "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); "
        "f = filedialog.askopenfilename(initialdir=sys.argv[1], title='Pilih File cookies.txt', "
        "filetypes=[('Text files', '*.txt'), ('All files', '*.*')]); "
        "root.destroy(); print(f or '')"
    )
    res = subprocess.run(
        [sys.executable, "-c", script, current],
        capture_output=True,
        text=True,
        timeout=120,
    )
    chosen = (res.stdout or "").strip()
    if chosen:
        database.set_setting("cookie_mode", "file")
        database.set_setting("cookie_file", chosen)
        return chosen
    return None


def open_folder_in_explorer(target_path: str | None = None) -> bool:
    """Open a directory in Windows Explorer."""
    path = Path(target_path).resolve() if target_path else get_download_dir()
    if not path.exists():
        path = get_download_dir()
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
            return True
        else:
            subprocess.run(["xdg-open", str(path)])
            return True
    except Exception:
        return False


def highlight_file_in_explorer(file_path: str) -> bool:
    """Select and highlight a specific downloaded file in Windows Explorer."""
    p = Path(file_path).resolve()
    if not p.is_file():
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer.exe", f"/select,{str(p)}"])
            return True
        else:
            return open_folder_in_explorer(str(p.parent))
    except Exception:
        return False


def get_system_status() -> dict[str, Any]:
    """Retrieve system diagnostics: FFmpeg status, yt-dlp version, disk space, and active queue."""
    _ensure_ffmpeg_path()
    ffmpeg_bin = shutil.which("ffmpeg")
    ffmpeg_ver = "-"
    if ffmpeg_bin:
        try:
            res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=5)
            first_line = (res.stdout or "").splitlines()[0] if res.stdout else "Installed"
            m = re.search(r"ffmpeg version\s+([^\s]+)", first_line)
            ffmpeg_ver = m.group(1) if m else "Installed"
        except Exception:
            ffmpeg_ver = "Installed"

    download_dir = get_download_dir()
    free_gb = 0.0
    try:
        total, used, free = shutil.disk_usage(download_dir)
        free_gb = round(free / (1024**3), 2)
    except Exception:
        pass

    with _TASKS_LOCK:
        active_count = sum(1 for t in _TASKS.values() if t.get("status") in ("downloading", "processing"))
        queued_count = sum(1 for t in _TASKS.values() if t.get("status") == "queued")

    return {
        "ffmpeg_installed": bool(ffmpeg_bin),
        "ffmpeg_version": ffmpeg_ver,
        "ffmpeg_path": ffmpeg_bin or "Tidak ditemukan",
        "ytdlp_version": getattr(yt_dlp.version, "__version__", "Terpasang"),
        "download_dir": str(download_dir),
        "free_disk_gb": free_gb,
        "active_downloads": active_count,
        "queued_downloads": queued_count,
        "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
    }


def check_ytdlp_update() -> dict[str, Any]:
    """Check latest yt-dlp version available on PyPI."""
    current = getattr(yt_dlp.version, "__version__", "unknown")
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "MediaDownloaderPro/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as res:
            data = json.loads(res.read().decode("utf-8"))
        latest = data.get("info", {}).get("version", current)
        update_available = latest != current and latest > current
        return {
            "current_version": current,
            "latest_version": latest,
            "update_available": update_available,
        }
    except Exception as exc:
        return {
            "current_version": current,
            "latest_version": current,
            "update_available": False,
            "error": str(exc),
        }


def upgrade_ytdlp() -> dict[str, Any]:
    """Upgrade yt-dlp via pip inside the current virtual environment."""
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if res.returncode != 0:
            return {
                "success": False,
                "error": res.stderr.strip() or res.stdout.strip() or "Pip upgrade gagal.",
            }

        # Reload module yt_dlp agar versi terupdate langsung aktif
        global yt_dlp
        importlib.reload(yt_dlp)
        importlib.reload(yt_dlp.version)
        new_ver = getattr(yt_dlp.version, "__version__", "unknown")

        return {
            "success": True,
            "new_version": new_ver,
            "output": res.stdout.strip(),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def auto_update_ytdlp_if_needed() -> None:
    """Check and perform background upgrade if auto-update is enabled in settings."""
    try:
        enabled = database.get_setting("auto_update_ytdlp", "true")
        if enabled.lower() != "true":
            return
        info = check_ytdlp_update()
        if info.get("update_available"):
            upgrade_ytdlp()
    except Exception:
        pass


def _apply_cookie_opts(ydl_opts: dict[str, Any]) -> None:
    cfg = get_cookie_settings()
    mode = cfg["cookie_mode"]
    if mode == "browser":
        browser = cfg["cookie_browser"]
        if browser in SUPPORTED_COOKIE_BROWSERS:
            ydl_opts["cookiesfrombrowser"] = (browser,)
    elif mode == "file":
        cfile = cfg["cookie_file"]
        if cfile and Path(cfile).is_file():
            ydl_opts["cookiefile"] = cfile


def _sanitize_filename(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return (cleaned[:max_len] or "media").strip(" .")


def _format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "-"
    total = int(seconds)
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _is_cookie_locked_error(err_str: str) -> bool:
    low = err_str.lower()
    return "could not copy" in low or "cookie database" in low or "permission denied" in low


def clean_media_url(url: str, as_playlist: bool = False) -> str:
    """Strip playlist and tracking parameters if user only wants the single video."""
    if not as_playlist and ("youtube.com/watch" in url or "youtu.be/" in url):
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "v" in qs:
            return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    return url


def inspect_url(url: str) -> dict[str, Any]:
    """Extract metadata, formats, and available resolutions without downloading."""
    _ensure_ffmpeg_path()

    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    single_video_id = qs.get("v", [None])[0]
    has_playlist_param = "list" in qs
    clean_single_url = f"https://www.youtube.com/watch?v={single_video_id}" if single_video_id else url

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": 50,  # Batasi inspeksi maksimal 50 video agar instan & tidak freeze di YouTube Mix
        "skip_download": True,
        "socket_timeout": 30,
        "retries": 5,
        "ignoreerrors": True,
        "nocheckcertificate": True,  # Bypass SSL check pada Android OpenSSL sandbox
        "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    }
    # Jika berjalan di Android, tambahkan player_client khusus YouTube
    if os.environ.get("ANDROID_FFMPEG_PATH") or os.environ.get("ANDROID_INTERNAL_DIR"):
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android", "ios", "mweb"]
            }
        }
    _apply_cookie_opts(ydl_opts)

    logger.log("INFO", f"Inspeksi URL: {url}", "INSPECT")
    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        msg = str(exc)
        logger.log("ERROR", f"Gagal inspeksi URL ({url}): {msg}", "INSPECT")
        # Jika browser sedang terbuka dan mengunci database cookies, coba fallback tanpa cookies
        if _is_cookie_locked_error(msg) and "cookiesfrombrowser" in ydl_opts:
            fallback_opts = dict(ydl_opts)
            fallback_opts.pop("cookiesfrombrowser", None)
            try:
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as inner_exc:
                inner_msg = str(inner_exc)
                if "bot" in inner_msg.lower() or "sign in" in inner_msg.lower() or "private" in inner_msg.lower():
                    raise ValueError(
                        "Browser Chrome sedang terbuka dan mengunci file cookies. "
                        "Silakan tutup sementara browser Google Chrome Anda, atau gunakan file cookies.txt di menu Pengaturan."
                    ) from inner_exc
                raise ValueError(f"Gagal memeriksa URL: {inner_msg}") from inner_exc
        elif "bot" in msg.lower() or "sign in" in msg.lower():
            raise ValueError(
                "YouTube meminta verifikasi / login. Silakan aktifkan opsi 'Autentikasi / Cookies' "
                "dari Browser di tab Pengaturan."
            ) from exc
        else:
            raise ValueError(f"Gagal memeriksa URL: {msg}") from exc

    if not info:
        raise ValueError("Tidak dapat mengambil informasi dari URL tersebut.")

    is_playlist = info.get("_type") == "playlist" or "entries" in info or has_playlist_param
    entries = list(info.get("entries") or []) if is_playlist else []

    playlist_videos = []
    thumbnail = info.get("thumbnail")

    if is_playlist and entries:
        for idx, entry in enumerate(entries, 1):
            if not entry:
                continue
            entry_duration = _format_duration(entry.get("duration"))
            entry_thumb = entry.get("thumbnail")
            if not entry_thumb:
                t_list = entry.get("thumbnails") or []
                entry_thumb = t_list[-1].get("url") if t_list else None

            playlist_videos.append(
                {
                    "index": idx,
                    "id": entry.get("id") or "",
                    "title": entry.get("title") or f"Video #{idx}",
                    "duration": entry_duration,
                    "thumbnail": entry_thumb,
                    "url": entry.get("url") or entry.get("webpage_url") or "",
                }
            )
        if not thumbnail and entries:
            first = entries[0] or {}
            thumbs = first.get("thumbnails") or []
            thumbnail = first.get("thumbnail") or (thumbs[-1].get("url") if thumbs else None)
    else:
        is_playlist = False
        playlist_videos.append(
            {
                "index": 1,
                "id": info.get("id") or "",
                "title": info.get("title") or "Video",
                "duration": _format_duration(info.get("duration")),
                "thumbnail": thumbnail,
                "url": url,
            }
        )

    resolutions: list[int] = []
    subtitles_available: list[str] = []

    if not is_playlist:
        heights = {
            int(fmt["height"])
            for fmt in (info.get("formats") or [])
            if fmt.get("height") and fmt.get("vcodec") != "none"
        }
        resolutions = sorted(heights, reverse=True)
        raw_subs = info.get("subtitles") or {}
        raw_auto = info.get("automatic_captions") or {}
        subtitles_available = sorted(list(set(list(raw_subs.keys()) + list(raw_auto.keys()))))
    else:
        resolutions = [1080, 720, 480, 360]

    return {
        "url": url,
        "clean_single_url": clean_single_url,
        "has_single_video": bool(single_video_id),
        "title": info.get("title") or (entries[0].get("title") if entries else "Playlist"),
        "platform": info.get("extractor_key") or info.get("extractor") or "Web",
        "uploader": info.get("uploader") or info.get("channel") or "-",
        "duration": _format_duration(info.get("duration")),
        "thumbnail": thumbnail,
        "is_playlist": is_playlist,
        "playlist_count": len(entries) if is_playlist else 1,
        "playlist_videos": playlist_videos,
        "resolutions": resolutions,
        "subtitles_available": subtitles_available,
    }


def get_task(task_id: str) -> dict[str, Any] | None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return None
        copy = dict(task)
        copy["items"] = [dict(it) for it in task.get("items", [])]
        return copy


def list_tasks() -> list[dict[str, Any]]:
    with _TASKS_LOCK:
        result = []
        for task in reversed(list(_TASKS.values())):
            copy = dict(task)
            copy["items"] = [dict(it) for it in task.get("items", [])]
            result.append(copy)
        return result


def _update_task(task_id: str, **fields: Any) -> None:
    with _TASKS_LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].update(fields)


def _update_task_item(
    task_id: str,
    item_index: int,
    item_title: str,
    item_status: str,
    item_progress: float,
) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        items: list[dict[str, Any]] = task.setdefault("items", [])
        idx = item_index if item_index > 0 else 1
        if not items:
            items.append(
                {
                    "index": idx,
                    "title": item_title,
                    "status": item_status,
                    "progress": item_progress,
                }
            )
            return

        matched = False
        for it in items:
            if it["index"] == idx:
                it["title"] = item_title or it["title"]
                it["status"] = item_status
                it["progress"] = item_progress
                matched = True
            elif it["index"] < idx and it["status"] in ("queued", "downloading", "processing"):
                it["status"] = "completed"
                it["progress"] = 100.0
        if not matched:
            items.append(
                {
                    "index": idx,
                    "title": item_title,
                    "status": item_status,
                    "progress": item_progress,
                }
            )


def _finalize_task_items(task_id: str, final_status: str) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        for it in task.get("items", []):
            if final_status == "completed":
                it["status"] = "completed"
                it["progress"] = 100.0
            elif it["status"] in ("downloading", "processing"):
                it["status"] = final_status


class DownloadCancelledError(Exception):
    """Raised when a user cancels an active download."""


def _is_cancelled(task_id: str) -> bool:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        return bool(task and task.get("cancelled"))


def cancel_download(task_id: str) -> bool:
    """Mark an active download task as cancelled."""
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return False
        if task["status"] in ("completed", "failed", "cancelled"):
            return False
        task["cancelled"] = True
        task["status_text"] = "Menghentikan unduhan..."
        return True


def start_download(
    url: str,
    format_type: str = "video",
    resolution: str = "best",
    audio_quality: str = "192",
    video_ext: str = "mp4",
    audio_format: str = "mp3",
    download_subtitles: bool = False,
    subtitles_lang: str = "id,en",
    embed_subtitles: bool = False,
    download_playlist: bool = False,
    playlist_items: str | None = None,
    output_dir: str | None = None,
    resume_task_dir: str | None = None,
    batch_id: str | None = None,
) -> str:
    """Queue a background download task and return its task_id."""
    task_id = uuid.uuid4().hex[:12]
    base_dir = Path(output_dir).resolve() if output_dir else get_download_dir()
    base_dir.mkdir(parents=True, exist_ok=True)

    # Bersihkan URL jika bukan download playlist agar tidak terbebani ratusan item YouTube Mix
    clean_target_url = clean_media_url(url, as_playlist=download_playlist)

    task_dir = resume_task_dir
    if download_playlist and not task_dir:
        task_dir = str(base_dir / f"playlist_{task_id}")

    chosen_format = audio_format if format_type == "audio" else video_ext

    with _TASKS_LOCK:
        _TASKS[task_id] = {
            "task_id": task_id,
            "batch_id": batch_id,
            "url": clean_target_url,
            "status": "queued",
            "status_text": "Menunggu antrian...",
            "progress": 0.0,
            "speed": "-",
            "eta": "-",
            "title": "Memproses...",
            "platform": "-",
            "format_type": format_type,
            "file_format": chosen_format,
            "resolution": resolution,
            "audio_quality": audio_quality,
            "video_ext": video_ext,
            "audio_format": audio_format,
            "download_subtitles": download_subtitles,
            "subtitles_lang": subtitles_lang,
            "embed_subtitles": embed_subtitles,
            "is_playlist": download_playlist,
            "playlist_items": playlist_items,
            "playlist_index": 0,
            "playlist_count": 0,
            "output_dir": str(base_dir),
            "task_dir": task_dir,
            "file_name": None,
            "file_path": None,
            "error": None,
            "cancelled": False,
            "items": [],
        }

    thread = threading.Thread(
        target=_worker_wrapper,
        args=(
            task_id,
            clean_target_url,
            format_type,
            resolution,
            audio_quality,
            video_ext,
            audio_format,
            download_subtitles,
            subtitles_lang,
            embed_subtitles,
            download_playlist,
            playlist_items,
            str(base_dir),
            task_dir,
            batch_id,
        ),
        daemon=True,
    )
    thread.start()
    return task_id


def start_batch_download(
    urls: list[str],
    format_type: str = "video",
    resolution: str = "best",
    audio_quality: str = "192",
    video_ext: str = "mp4",
    audio_format: str = "mp3",
    download_subtitles: bool = False,
    subtitles_lang: str = "id,en",
    embed_subtitles: bool = False,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Queue multiple URLs as a batch download group."""
    batch_id = uuid.uuid4().hex[:8]
    valid_urls = [u.strip() for u in urls if u and u.strip().startswith(("http://", "https://"))]
    if not valid_urls:
        raise ValueError("Tidak ada URL valid yang diberikan.")

    task_ids = []
    for u in valid_urls:
        t_id = start_download(
            url=u,
            format_type=format_type,
            resolution=resolution,
            audio_quality=audio_quality,
            video_ext=video_ext,
            audio_format=audio_format,
            download_subtitles=download_subtitles,
            subtitles_lang=subtitles_lang,
            embed_subtitles=embed_subtitles,
            download_playlist=False,
            output_dir=output_dir,
            batch_id=batch_id,
        )
        task_ids.append(t_id)

    return {
        "batch_id": batch_id,
        "total": len(task_ids),
        "task_ids": task_ids,
    }


def resume_task(task_id: str) -> str:
    """Create a new download task resuming from an existing task's parameters & folder."""
    task = get_task(task_id)
    if not task:
        raise ValueError("Task tidak ditemukan.")
    return start_download(
        url=task["url"],
        format_type=task.get("format_type", "video"),
        resolution=task.get("resolution", "best"),
        audio_quality=task.get("audio_quality", "192"),
        video_ext=task.get("video_ext", "mp4"),
        audio_format=task.get("audio_format", "mp3"),
        download_subtitles=bool(task.get("download_subtitles")),
        subtitles_lang=task.get("subtitles_lang", "id,en"),
        embed_subtitles=bool(task.get("embed_subtitles")),
        download_playlist=bool(task.get("is_playlist")),
        playlist_items=task.get("playlist_items"),
        output_dir=task.get("output_dir"),
        resume_task_dir=task.get("task_dir"),
        batch_id=task.get("batch_id"),
    )


def resume_from_history(history_id: int) -> str:
    """Resume a cancelled or failed download from a history record."""
    item = database.get_history_item(history_id)
    if not item:
        raise ValueError("Riwayat tidak ditemukan.")
    raw_res = item.get("resolution") or "best"
    if raw_res in ("Terbaik", "best") or raw_res.startswith("MP3") or "kbps" in raw_res:
        res_val = "best"
    else:
        res_val = raw_res.rstrip("p") if raw_res.endswith("p") and raw_res[:-1].isdigit() else "best"

    fmt_type = item.get("format_type", "video")
    saved_fmt = item.get("file_format", "")
    video_ext = saved_fmt if (fmt_type == "video" and saved_fmt in ("mp4", "mkv", "webm")) else "mp4"
    audio_fmt = saved_fmt if (fmt_type == "audio" and saved_fmt) else "mp3"

    return start_download(
        url=item["url"],
        format_type=fmt_type,
        resolution=res_val,
        audio_quality=item.get("audio_quality") or "192",
        video_ext=video_ext,
        audio_format=audio_fmt,
        download_subtitles=bool(item.get("subtitles")),
        subtitles_lang="id,en",
        embed_subtitles=False,
        download_playlist=bool(item.get("is_playlist")),
        playlist_items=item.get("playlist_items"),
        output_dir=item.get("output_dir"),
        resume_task_dir=item.get("task_dir"),
        batch_id=item.get("batch_id"),
    )


def _worker_wrapper(
    task_id: str,
    url: str,
    format_type: str,
    resolution: str,
    audio_quality: str,
    video_ext: str,
    audio_format: str,
    download_subtitles: bool,
    subtitles_lang: str,
    embed_subtitles: bool,
    download_playlist: bool,
    playlist_items: str | None,
    output_dir: str,
    task_dir: str | None,
    batch_id: str | None,
) -> None:
    """Wait for concurrency semaphore slot and run download."""
    if _is_cancelled(task_id):
        _finalize_task_items(task_id, "cancelled")
        _update_task(task_id, status="cancelled", status_text="Dibatalkan saat antrian.")
        return

    with _SEMAPHORE:
        if _is_cancelled(task_id):
            _finalize_task_items(task_id, "cancelled")
            _update_task(task_id, status="cancelled", status_text="Dibatalkan saat antrian.")
            return

        _run_download(
            task_id=task_id,
            url=url,
            format_type=format_type,
            resolution=resolution,
            audio_quality=audio_quality,
            video_ext=video_ext,
            audio_format=audio_format,
            download_subtitles=download_subtitles,
            subtitles_lang=subtitles_lang,
            embed_subtitles=embed_subtitles,
            download_playlist=download_playlist,
            playlist_items=playlist_items,
            output_dir=output_dir,
            task_dir=task_dir,
            batch_id=batch_id,
        )


def _run_download(
    task_id: str,
    url: str,
    format_type: str,
    resolution: str,
    audio_quality: str,
    video_ext: str,
    audio_format: str,
    download_subtitles: bool,
    subtitles_lang: str,
    embed_subtitles: bool,
    download_playlist: bool,
    playlist_items: str | None,
    output_dir: str,
    task_dir: str | None,
    batch_id: str | None,
) -> None:
    _ensure_ffmpeg_path()
    title = "Media"
    platform = "Web"
    is_playlist_actual = False
    base_dir = Path(output_dir)
    target_dir = Path(task_dir) if (download_playlist and task_dir) else base_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: list[Path] = []
    chosen_file_format = audio_format if format_type == "audio" else video_ext

    def progress_hook(d: dict[str, Any]) -> None:
        if _is_cancelled(task_id):
            raise DownloadCancelledError("Unduhan dibatalkan oleh pengguna.")
        status = d.get("status")
        info = d.get("info_dict") or {}
        p_idx = info.get("playlist_index") or 0
        p_count = info.get("n_entries") or info.get("playlist_count") or 0
        item_title = info.get("title") or title

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = round((downloaded / total) * 100, 1) if total else 0.0
            speed_val = d.get("speed")
            speed_str = f"{speed_val / (1024 * 1024):.2f} MB/s" if speed_val else "-"
            eta_val = d.get("eta")
            eta_str = f"{int(eta_val)}s" if eta_val is not None else "-"
            _update_task_item(task_id, p_idx or 1, item_title, "downloading", pct)
            _update_task(
                task_id,
                status="downloading",
                status_text=f"Mengunduh: {item_title}",
                progress=pct,
                speed=speed_str,
                eta=eta_str,
                playlist_index=p_idx,
                playlist_count=p_count,
            )
        elif status == "finished":
            filename = d.get("filename")
            if filename:
                downloaded_files.append(Path(filename))
            _update_task_item(task_id, p_idx or 1, item_title, "processing", 99.0)
            _update_task(
                task_id,
                status="processing",
                status_text="Memproses & menggabungkan file (FFmpeg)...",
                progress=99.0,
                speed="-",
                eta="-",
            )

    def postprocessor_hook(d: dict[str, Any]) -> None:
        if _is_cancelled(task_id):
            raise DownloadCancelledError("Unduhan dibatalkan oleh pengguna.")
        if d.get("status") == "finished":
            filepath = (d.get("info_dict") or {}).get("filepath")
            if filepath:
                downloaded_files.append(Path(filepath))

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not download_playlist,
        "continuedl": True,
        "nopart": False,
        "socket_timeout": 60,
        "retries": 15,
        "fragment_retries": 15,
        "file_access_retries": 5,
        "extractor_retries": 5,
        "ignoreerrors": "only_download" if download_playlist else False,
        "nocheckcertificate": True,  # Mengatasi SSL: CERTIFICATE_VERIFY_FAILED di sandbox Android untuk TikTok/IG/FB/Twitter
        "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "outtmpl": str(target_dir / "%(title).80s [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }
    # Jika berjalan di Android, set lokasi binary ffmpeg dan extractor-args mobile client
    android_ffmpeg = os.environ.get("ANDROID_FFMPEG_PATH")
    if android_ffmpeg and os.path.isfile(android_ffmpeg):
        ydl_opts["ffmpeg_location"] = android_ffmpeg
        logger.log("INFO", f"Menggunakan FFmpeg Android di: {android_ffmpeg}", "DOWNLOAD")
    else:
        logger.log("WARN", f"FFmpeg Android belum terdeteksi (ANDROID_FFMPEG_PATH={android_ffmpeg})", "DOWNLOAD")
        # YouTube sering memblokir web client di Android (karena ketiadaan JS runtime seperti node/deno).
        # Gunakan extractor-args android & ios mobile client agar tidak terkena 'n challenge' atau 403 Forbidden
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android", "ios", "mweb"]
            }
        }

    _apply_cookie_opts(ydl_opts)

    if download_playlist and playlist_items:
        ydl_opts["playlist_items"] = playlist_items.strip()

    # Opsi Subtitle / Caption
    if download_subtitles:
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        lang_str = subtitles_lang.strip() if subtitles_lang else "id,en"
        if lang_str.lower() != "all":
            ydl_opts["subtitleslangs"] = [l.strip() for l in lang_str.split(",") if l.strip()]
        ydl_opts["subtitlesformat"] = "srt/vtt/best"

    # Konfigurasi Audio vs Video
    if format_type == "audio":
        ydl_opts["format"] = "bestaudio/best"
        codec = audio_format.lower() if audio_format.lower() in ("mp3", "m4a", "wav", "flac", "aac", "opus") else "mp3"
        postproc: dict[str, Any] = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": codec,
        }
        if codec in ("mp3", "m4a", "opus"):
            postproc["preferredquality"] = audio_quality if audio_quality in ("128", "192", "256", "320") else "192"
        ydl_opts["postprocessors"] = [postproc]
        res_label = f"{codec.upper()} {audio_quality}kbps"
    else:
        # Video format
        target_ext = video_ext.lower() if video_ext.lower() in ("mp4", "mkv", "webm") else "mp4"
        if resolution == "best":
            # Coba format single (pre-merged video+audio) terlebih dahulu (b / best) sebagai fallback jika FFmpeg tidak tersedia
            ydl_opts["format"] = (
                f"bestvideo[ext={target_ext}]+bestaudio/bestvideo+bestaudio/best[ext={target_ext}]/b/best"
            )
            res_label = "Terbaik"
        else:
            h = int(resolution)
            ydl_opts["format"] = (
                f"bestvideo[height<={h}][ext={target_ext}]+bestaudio/"
                f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/b[height<={h}]/best"
            )
            res_label = f"{h}p"
        ydl_opts["merge_output_format"] = target_ext

        # Embed subtitle ke video jika diminta
        if download_subtitles and embed_subtitles and target_ext in ("mp4", "mkv"):
            ydl_opts.setdefault("postprocessors", []).append({
                "key": "FFmpegEmbedSubtitle",
                "already_have_subtitle": False,
            })

    try:
        _update_task(task_id, status="downloading", status_text="Mengambil metadata...")
        pre_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "noplaylist": not download_playlist,
            "socket_timeout": 30,
            "retries": 5,
            "ignoreerrors": True,
        }
        if download_playlist and playlist_items:
            pre_opts["playlist_items"] = playlist_items.strip()
        _apply_cookie_opts(pre_opts)

        try:
            with yt_dlp.YoutubeDL(pre_opts) as pre_ydl:
                pre_info = pre_ydl.extract_info(url, download=False)
        except Exception as pre_exc:
            if _is_cookie_locked_error(str(pre_exc)) and "cookiesfrombrowser" in pre_opts:
                try:
                    fallback_pre = dict(pre_opts)
                    fallback_pre.pop("cookiesfrombrowser", None)
                    with yt_dlp.YoutubeDL(fallback_pre) as pre_ydl:
                        pre_info = pre_ydl.extract_info(url, download=False)
                except Exception:
                    pass

        if pre_info:
            title = pre_info.get("title") or title
            platform = pre_info.get("extractor_key") or pre_info.get("extractor") or platform
            if download_playlist and "entries" in pre_info:
                raw_entries = [e for e in (pre_info.get("entries") or []) if e]
                queued_items = [
                    {
                        "index": idx + 1,
                        "title": entry.get("title") or f"Item {idx + 1}",
                        "status": "queued",
                        "progress": 0.0,
                    }
                    for idx, entry in enumerate(raw_entries)
                ]
                _update_task(
                    task_id,
                    title=title,
                    platform=platform,
                    playlist_count=len(queued_items),
                    items=queued_items,
                )
            else:
                _update_task(
                    task_id,
                    title=title,
                    platform=platform,
                    items=[{"index": 1, "title": title, "status": "queued", "progress": 0.0}],
                )

        if _is_cancelled(task_id):
            raise DownloadCancelledError("Unduhan dibatalkan oleh pengguna.")

        info = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            msg = str(exc)
            if _is_cookie_locked_error(msg) and "cookiesfrombrowser" in ydl_opts:
                fallback_ydl_opts = dict(ydl_opts)
                fallback_ydl_opts.pop("cookiesfrombrowser", None)
                with yt_dlp.YoutubeDL(fallback_ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
            else:
                raise

        if info:
            title = info.get("title") or title
            platform = info.get("extractor_key") or info.get("extractor") or platform
            is_playlist_actual = info.get("_type") == "playlist" or "entries" in info

        final_file: Path | None = None

        if download_playlist:
            zip_base = base_dir / f"{_sanitize_filename(title)}_{task_id[:6]}"
            zip_path = Path(shutil.make_archive(str(zip_base), "zip", str(target_dir)))
            final_file = zip_path
        else:
            existing = [p for p in reversed(downloaded_files) if p.exists()]
            if existing:
                final_file = existing[0]
            elif info:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    candidate = Path(ydl.prepare_filename(info))
                    if format_type == "audio":
                        candidate = candidate.with_suffix(f".{chosen_file_format}")
                    elif candidate.with_suffix(f".{chosen_file_format}").exists():
                        candidate = candidate.with_suffix(f".{chosen_file_format}")
                    if candidate.exists():
                        final_file = candidate

        file_name = final_file.name if final_file and final_file.exists() else None
        file_path = str(final_file) if final_file and final_file.exists() else None
        file_size = final_file.stat().st_size if final_file and final_file.exists() else 0

        # Jika di Android, pastikan file tersalin/terindeks ke folder Download publik HP
        android_download = os.environ.get("ANDROID_DOWNLOAD_DIR")
        if final_file and final_file.exists() and android_download:
            try:
                target_public_dir = Path(android_download)
                target_public_dir.mkdir(parents=True, exist_ok=True)
                dest_file = target_public_dir / final_file.name
                if final_file.resolve() != dest_file.resolve():
                    shutil.copy2(str(final_file), str(dest_file))
                    file_path = str(dest_file)
            except Exception:
                pass

        # Trigger MediaScanner di Android agar file langsung muncul di Galeri / File Manager HP
        if file_path:
            try:
                from com.chaquo.python import Python
                current_activity = Python.getPlatform().getApplicationContext()
                from android.media import MediaScannerConnection
                MediaScannerConnection.scanFile(current_activity, [file_path], None, None)
            except Exception:
                pass

        database.add_history(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format_type": format_type,
                "resolution": res_label,
                "audio_quality": audio_quality,
                "file_format": chosen_file_format,
                "subtitles": subtitles_lang if download_subtitles else "",
                "batch_id": batch_id,
                "is_playlist": is_playlist_actual or download_playlist,
                "playlist_items": playlist_items,
                "output_dir": str(base_dir),
                "task_dir": str(target_dir) if download_playlist else None,
                "file_name": file_name,
                "file_path": file_path,
                "file_size": file_size,
                "status": "completed",
                "error_message": None,
            }
        )

        _finalize_task_items(task_id, "completed")
        logger.log("INFO", f"Unduhan sukses: '{title}' -> {file_path}", "DOWNLOAD")
        _update_task(
            task_id,
            status="completed",
            status_text="Unduhan selesai!",
            progress=100.0,
            title=title,
            platform=platform,
            is_playlist=is_playlist_actual or download_playlist,
            file_name=file_name,
            file_path=file_path,
        )
    except DownloadCancelledError:
        _finalize_task_items(task_id, "cancelled")
        database.add_history(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format_type": format_type,
                "resolution": res_label,
                "audio_quality": audio_quality,
                "file_format": chosen_file_format,
                "subtitles": subtitles_lang if download_subtitles else "",
                "batch_id": batch_id,
                "is_playlist": download_playlist,
                "playlist_items": playlist_items,
                "output_dir": str(base_dir),
                "task_dir": str(target_dir) if download_playlist else None,
                "file_name": None,
                "file_path": None,
                "file_size": 0,
                "status": "cancelled",
                "error_message": "Dihentikan oleh pengguna",
            }
        )
        _update_task(
            task_id,
            status="cancelled",
            status_text="Unduhan dihentikan (bisa di-Resume).",
            speed="-",
            eta="-",
        )
    except Exception as exc:
        raw_err = str(exc)
        logger.log("ERROR", f"Unduhan gagal ({url}): {raw_err}", "DOWNLOAD")
        if "10054" in raw_err or "forcibly closed" in raw_err.lower():
            err_msg = "Koneksi terputus dari YouTube (WinError 10054). YouTube memutus koneksi saat mengunduh batch/playlist besar. Disarankan mengunduh video satu per satu atau membatasi rentang playlist (misal: 1-5)."
        elif "timed out" in raw_err.lower():
            err_msg = "Waktu koneksi habis (Timeout). Koneksi internet lambat atau terputus saat mengunduh dari server YouTube."
        elif "not available" in raw_err.lower():
            err_msg = "Video tidak tersedia atau telah dihapus oleh pengunggah di YouTube."
        elif "bot" in raw_err.lower() or "sign in" in raw_err.lower():
            err_msg = "Akses diblokir (Sign in / Bot check). Aktifkan Cookies Browser di menu Pengaturan."
        elif "private" in raw_err.lower():
            err_msg = "Konten bersifat privat atau memerlukan autentikasi login."
        elif "ffmpeg" in raw_err.lower():
            err_msg = "FFmpeg diperlukan untuk menggabungkan/mengonversi format ini."
        else:
            err_msg = raw_err[:300]

        _finalize_task_items(task_id, "failed")
        database.add_history(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format_type": format_type,
                "resolution": res_label,
                "audio_quality": audio_quality,
                "file_format": chosen_file_format,
                "subtitles": subtitles_lang if download_subtitles else "",
                "batch_id": batch_id,
                "is_playlist": download_playlist,
                "playlist_items": playlist_items,
                "output_dir": str(base_dir),
                "task_dir": str(target_dir) if download_playlist else None,
                "file_name": None,
                "file_path": None,
                "file_size": 0,
                "status": "failed",
                "error_message": err_msg,
            }
        )
        _update_task(
            task_id,
            status="failed",
            status_text="Gagal mengunduh",
            error=err_msg,
        )

"""yt-dlp wrapper and background task manager for media downloads."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from app import database

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

_TASKS_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}


def get_download_dir() -> Path:
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
    """Open a native folder picker dialog via a short-lived Python subprocess."""
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


SUPPORTED_COOKIE_BROWSERS = {"chrome", "edge", "firefox", "brave", "opera"}


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


def inspect_url(url: str) -> dict[str, Any]:
    """Extract metadata and available resolutions without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    _apply_cookie_opts(ydl_opts)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("Tidak dapat mengambil informasi dari URL tersebut.")

    is_playlist = info.get("_type") == "playlist" or "entries" in info
    entries = list(info.get("entries") or []) if is_playlist else []

    playlist_videos = []
    if is_playlist:
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
    else:
        # Jika single video, masukkan ke list agar bisa dilihat sebelum download
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
    if not is_playlist:
        heights = {
            int(fmt["height"])
            for fmt in (info.get("formats") or [])
            if fmt.get("height") and fmt.get("vcodec") != "none"
        }
        resolutions = sorted(heights, reverse=True)

    thumbnail = info.get("thumbnail")
    if not thumbnail and entries:
        first = entries[0] or {}
        thumbs = first.get("thumbnails") or []
        thumbnail = first.get("thumbnail") or (thumbs[-1].get("url") if thumbs else None)

    return {
        "url": url,
        "title": info.get("title") or "Tanpa Judul",
        "platform": info.get("extractor_key") or info.get("extractor") or "Web",
        "uploader": info.get("uploader") or info.get("channel") or "-",
        "duration": _format_duration(info.get("duration")),
        "thumbnail": thumbnail,
        "is_playlist": is_playlist,
        "playlist_count": len(entries) if is_playlist else 1,
        "playlist_videos": playlist_videos,
        "resolutions": resolutions,
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
    download_playlist: bool = False,
    playlist_items: str | None = None,
    output_dir: str | None = None,
    resume_task_dir: str | None = None,
) -> str:
    """Queue a background download task and return its task_id."""
    task_id = uuid.uuid4().hex[:12]
    base_dir = Path(output_dir).resolve() if output_dir else get_download_dir()
    base_dir.mkdir(parents=True, exist_ok=True)

    task_dir = resume_task_dir
    if download_playlist and not task_dir:
        task_dir = str(base_dir / f"playlist_{task_id}")

    with _TASKS_LOCK:
        _TASKS[task_id] = {
            "task_id": task_id,
            "url": url,
            "status": "queued",
            "status_text": "Menyiapkan unduhan...",
            "progress": 0.0,
            "speed": "-",
            "eta": "-",
            "title": "Memproses...",
            "platform": "-",
            "format_type": format_type,
            "resolution": resolution,
            "audio_quality": audio_quality,
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
        target=_run_download,
        args=(
            task_id,
            url,
            format_type,
            resolution,
            audio_quality,
            download_playlist,
            playlist_items,
            str(base_dir),
            task_dir,
        ),
        daemon=True,
    )
    thread.start()
    return task_id


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
        download_playlist=bool(task.get("is_playlist")),
        playlist_items=task.get("playlist_items"),
        output_dir=task.get("output_dir"),
        resume_task_dir=task.get("task_dir"),
    )


def resume_from_history(history_id: int) -> str:
    """Resume a cancelled or failed download from a history record."""
    item = database.get_history_item(history_id)
    if not item:
        raise ValueError("Riwayat tidak ditemukan.")
    raw_res = item.get("resolution") or "best"
    if raw_res in ("Terbaik", "best") or raw_res.startswith("MP3"):
        res_val = "best"
    else:
        res_val = raw_res.rstrip("p") if raw_res.endswith("p") and raw_res[:-1].isdigit() else "best"
    return start_download(
        url=item["url"],
        format_type=item.get("format_type", "video"),
        resolution=res_val,
        audio_quality=item.get("audio_quality") or "192",
        download_playlist=bool(item.get("is_playlist")),
        playlist_items=item.get("playlist_items"),
        output_dir=item.get("output_dir"),
        resume_task_dir=item.get("task_dir"),
    )


def _run_download(
    task_id: str,
    url: str,
    format_type: str,
    resolution: str,
    audio_quality: str,
    download_playlist: bool,
    playlist_items: str | None,
    output_dir: str,
    task_dir: str | None,
) -> None:
    title = "Media"
    platform = "Web"
    is_playlist_actual = False
    base_dir = Path(output_dir)
    target_dir = Path(task_dir) if (download_playlist and task_dir) else base_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: list[Path] = []

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
                status_text="Memproses / mengonversi media dengan FFmpeg...",
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
        "outtmpl": str(target_dir / "%(title).80s [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }
    _apply_cookie_opts(ydl_opts)

    if download_playlist and playlist_items:
        ydl_opts["playlist_items"] = playlist_items.strip()

    if format_type == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }
        ]
        res_label = f"MP3 {audio_quality}kbps"
    else:
        if resolution == "best":
            ydl_opts["format"] = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            )
            res_label = "Terbaik"
        else:
            h = int(resolution)
            ydl_opts["format"] = (
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
            )
            res_label = f"{h}p"
        ydl_opts["merge_output_format"] = "mp4"

    try:
        _update_task(task_id, status="downloading", status_text="Mengambil metadata...")
        pre_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "noplaylist": not download_playlist,
        }
        if download_playlist and playlist_items:
            pre_opts["playlist_items"] = playlist_items.strip()
        _apply_cookie_opts(pre_opts)
        try:
            with yt_dlp.YoutubeDL(pre_opts) as pre_ydl:
                pre_info = pre_ydl.extract_info(url, download=False)
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
        except Exception:
            pass

        if _is_cancelled(task_id):
            raise DownloadCancelledError("Unduhan dibatalkan oleh pengguna.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

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
                        candidate = candidate.with_suffix(".mp3")
                    elif candidate.with_suffix(".mp4").exists():
                        candidate = candidate.with_suffix(".mp4")
                    if candidate.exists():
                        final_file = candidate

        file_name = final_file.name if final_file and final_file.exists() else None
        file_path = str(final_file) if final_file and final_file.exists() else None
        file_size = final_file.stat().st_size if final_file and final_file.exists() else 0

        database.add_history(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format_type": format_type,
                "resolution": res_label,
                "audio_quality": audio_quality,
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
        err_msg = str(exc)
        _finalize_task_items(task_id, "failed")
        database.add_history(
            {
                "url": url,
                "title": title,
                "platform": platform,
                "format_type": format_type,
                "resolution": res_label,
                "audio_quality": audio_quality,
                "is_playlist": download_playlist,
                "playlist_items": playlist_items,
                "output_dir": str(base_dir),
                "task_dir": str(target_dir) if download_playlist else None,
                "file_name": None,
                "file_path": None,
                "file_size": 0,
                "status": "failed",
                "error_message": err_msg[:300],
            }
        )
        _update_task(
            task_id,
            status="failed",
            status_text="Gagal mengunduh",
            error=err_msg,
        )

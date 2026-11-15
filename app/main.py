"""FastAPI application for the multi-platform media downloader."""

from __future__ import annotations

import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import database, downloader, logger

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.init_db()
    # Cek auto-update yt-dlp di background thread saat startup jika diaktifkan
    threading.Thread(target=downloader.auto_update_ytdlp_if_needed, daemon=True).start()
    yield


app = FastAPI(title="Media Downloader Web App", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class InspectRequest(BaseModel):
    url: str = Field(..., min_length=5)


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=5)
    format_type: Literal["video", "audio"] = "video"
    resolution: str = "best"
    audio_quality: Literal["128", "192", "256", "320"] = "192"
    video_ext: Literal["mp4", "mkv", "webm"] = "mp4"
    audio_format: Literal["mp3", "m4a", "wav", "flac", "aac", "opus"] = "mp3"
    download_subtitles: bool = False
    subtitles_lang: str = "id,en"
    embed_subtitles: bool = False
    download_playlist: bool = False
    playlist_items: str | None = None
    output_dir: str | None = None


class BatchDownloadRequest(BaseModel):
    urls: list[str] = Field(..., min_items=1)
    format_type: Literal["video", "audio"] = "video"
    resolution: str = "best"
    audio_quality: Literal["128", "192", "256", "320"] = "192"
    video_ext: Literal["mp4", "mkv", "webm"] = "mp4"
    audio_format: Literal["mp3", "m4a", "wav", "flac", "aac", "opus"] = "mp3"
    download_subtitles: bool = False
    subtitles_lang: str = "id,en"
    embed_subtitles: bool = False
    output_dir: str | None = None


class FolderRequest(BaseModel):
    download_dir: str = Field(..., min_length=1)


class CookieSettingsRequest(BaseModel):
    cookie_mode: Literal["none", "browser", "file"] = "none"
    cookie_browser: Literal["chrome", "edge", "firefox", "brave", "opera", "vivaldi"] = "chrome"
    cookie_file: str = ""


class OpenFileRequest(BaseModel):
    file_path: str = Field(..., min_length=1)


class AutoUpdateRequest(BaseModel):
    enabled: bool


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/inspect")
def inspect_media(req: InspectRequest):
    try:
        return downloader.inspect_url(req.url.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/download")
def start_media_download(req: DownloadRequest):
    if req.format_type == "video" and req.resolution != "best":
        if not req.resolution.isdigit():
            raise HTTPException(status_code=400, detail="Resolusi tidak valid.")
    task_id = downloader.start_download(
        url=req.url.strip(),
        format_type=req.format_type,
        resolution=req.resolution,
        audio_quality=req.audio_quality,
        video_ext=req.video_ext,
        audio_format=req.audio_format,
        download_subtitles=req.download_subtitles,
        subtitles_lang=req.subtitles_lang,
        embed_subtitles=req.embed_subtitles,
        download_playlist=req.download_playlist,
        playlist_items=req.playlist_items,
        output_dir=req.output_dir,
    )
    return {"task_id": task_id}


@app.post("/api/batch-download")
def start_batch_download(req: BatchDownloadRequest):
    try:
        return downloader.start_batch_download(
            urls=req.urls,
            format_type=req.format_type,
            resolution=req.resolution,
            audio_quality=req.audio_quality,
            video_ext=req.video_ext,
            audio_format=req.audio_format,
            download_subtitles=req.download_subtitles,
            subtitles_lang=req.subtitles_lang,
            embed_subtitles=req.embed_subtitles,
            output_dir=req.output_dir,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/stats")
def get_dashboard_stats():
    return database.get_history_stats()


@app.get("/api/system-status")
def get_system_diagnostics():
    return downloader.get_system_status()


@app.get("/api/ytdlp/check-update")
def check_ytdlp_update():
    return downloader.check_ytdlp_update()


@app.post("/api/ytdlp/update")
def trigger_ytdlp_update():
    res = downloader.upgrade_ytdlp()
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Gagal mengupdate yt-dlp."))
    return res


@app.get("/api/settings/auto-update")
def get_auto_update_setting():
    val = database.get_setting("auto_update_ytdlp", "true")
    return {"enabled": val.lower() == "true"}


@app.post("/api/settings/auto-update")
def set_auto_update_setting(req: AutoUpdateRequest):
    database.set_setting("auto_update_ytdlp", "true" if req.enabled else "false")
    return {"enabled": req.enabled}


@app.post("/api/open-folder")
def open_download_folder():
    ok = downloader.open_folder_in_explorer()
    return {"opened": ok, "folder": str(downloader.get_download_dir())}


@app.post("/api/open-file")
def open_file_in_folder(req: OpenFileRequest):
    ok = downloader.highlight_file_in_explorer(req.file_path)
    return {"opened": ok}


@app.get("/api/settings")
def get_settings():
    return {
        "download_dir": str(downloader.get_download_dir()),
        **downloader.get_cookie_settings(),
    }


@app.post("/api/settings/cookies")
def update_cookie_settings(req: CookieSettingsRequest):
    return downloader.set_cookie_settings(
        cookie_mode=req.cookie_mode,
        cookie_browser=req.cookie_browser,
        cookie_file=req.cookie_file,
    )


@app.post("/api/settings/pick-cookies")
def pick_cookies_file():
    try:
        chosen = downloader.pick_cookies_file_dialog()
        return {
            "selected": bool(chosen),
            **downloader.get_cookie_settings(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal membuka dialog file: {exc}") from exc


@app.post("/api/settings/folder")
def update_download_folder(req: FolderRequest):
    try:
        saved = downloader.set_download_dir(req.download_dir)
        return {"download_dir": str(saved)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Folder tidak valid: {exc}") from exc


@app.post("/api/settings/pick-folder")
def pick_download_folder():
    try:
        chosen = downloader.pick_folder_dialog()
        return {
            "selected": bool(chosen),
            "download_dir": chosen or str(downloader.get_download_dir()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal membuka dialog folder: {exc}") from exc


@app.get("/api/tasks")
def list_all_tasks():
    return {"tasks": downloader.list_tasks()}


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str):
    task = downloader.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan.")
    return task


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    task = downloader.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan.")
    cancelled = downloader.cancel_download(task_id)
    return {"cancelled": cancelled}


@app.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    try:
        new_task_id = downloader.resume_task(task_id)
        return {"task_id": new_task_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tasks/{task_id}/file")
def download_task_file(task_id: str):
    task = downloader.get_task(task_id)
    if not task or not task.get("file_path"):
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    target = Path(task["file_path"]).resolve()
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")


@app.get("/api/tasks/{task_id}/download-stream")
def stream_and_cleanup_task(task_id: str, background_tasks: BackgroundTasks):
    """Stream file to client and delete file from server storage once streaming is finished."""
    task = downloader.get_task(task_id)
    if not task or not task.get("file_path"):
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    target = Path(task["file_path"]).resolve()
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File fisik sudah dihapus dari server.")

    def cleanup_file(p: Path):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
            # Bersihkan folder tugas playlist jika ada
            if p.parent != downloader.get_download_dir() and (p.parent.name.startswith("playlist_") or p.parent.name.startswith("task_")):
                shutil.rmtree(p.parent, ignore_errors=True)
        except Exception:
            pass

    background_tasks.add_task(cleanup_file, target)
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/octet-stream",
    )


@app.post("/api/settings/upload-cookies")
async def upload_cookies_file(file: UploadFile = File(...)):
    """Upload Netscape cookies.txt file directly via web interface (server/cloud ready)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File tidak valid.")
    save_path = downloader.DOWNLOADS_DIR / "cookies.txt"
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    downloader.set_cookie_settings(
        cookie_mode="file",
        cookie_file=str(save_path),
    )
    return {"success": True, "cookie_file": str(save_path)}


@app.get("/api/history")
def get_history(
    search: str | None = Query(None),
    status: str | None = Query(None),
    platform: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    items = database.list_history(limit=limit, search=search, status=status, platform=platform)
    for item in items:
        fpath = item.get("file_path")
        fname = item.get("file_name")
        exists = bool(fpath and Path(fpath).is_file())
        if not exists and fname:
            exists = (downloader.get_download_dir() / fname).is_file() or (downloader.DOWNLOADS_DIR / fname).is_file()
        item["file_exists"] = exists
    return {"items": items}


@app.post("/api/history/{item_id}/resume")
def resume_history_item(item_id: int):
    try:
        new_task_id = downloader.resume_from_history(item_id)
        return {"task_id": new_task_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/history/{item_id}/file")
def download_history_file(item_id: int):
    item = database.get_history_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    fpath = item.get("file_path")
    target = Path(fpath).resolve() if fpath else None
    if not target or not target.is_file():
        fname = item.get("file_name")
        if fname:
            for base in (downloader.get_download_dir(), downloader.DOWNLOADS_DIR):
                candidate = (base / Path(fname).name).resolve()
                if candidate.is_file():
                    target = candidate
                    break
    if not target or not target.is_file():
        raise HTTPException(status_code=404, detail="File fisik sudah dihapus atau dipindahkan.")
    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")


@app.delete("/api/history/{item_id}")
def remove_history_item(item_id: int):
    if not database.delete_history_item(item_id):
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan.")
    return {"deleted": True}


@app.delete("/api/history")
def clear_all_history():
    count = database.clear_history()
    return {"deleted_count": count}


@app.get("/api/files/{file_name}")
def download_file(file_name: str):
    safe_name = Path(file_name).name
    target = (downloader.DOWNLOADS_DIR / safe_name).resolve()
    if target.parent != downloader.DOWNLOADS_DIR.resolve() or not target.is_file():
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    return FileResponse(path=target, filename=safe_name, media_type="application/octet-stream")


@app.get("/api/logs")
def get_system_logs(limit: int = 200):
    """Retrieve system diagnostics and error logs."""
    return {"logs": logger.get_logs(limit=limit)}


@app.delete("/api/logs")
def clear_system_logs():
    """Clear all stored logs."""
    logger.clear_logs()
    return {"cleared": True}


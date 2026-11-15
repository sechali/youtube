"""In-memory and file-based rolling logger for diagnostics."""

from __future__ import annotations

import collections
import datetime
import os
import threading
from pathlib import Path

# Maksimal baris log yang disimpan di RAM
MAX_LOG_ENTRIES = 300

_LOGS_LOCK = threading.Lock()
_LOG_BUFFER: collections.deque[dict[str, str]] = collections.deque(maxlen=MAX_LOG_ENTRIES)

# Lokasi file log
_android_internal = os.environ.get("ANDROID_INTERNAL_DIR")
if _android_internal:
    LOG_FILE_PATH = Path(_android_internal) / "app.log"
else:
    LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "app.log"


def log(level: str, message: str, category: str = "GENERAL") -> None:
    """Record a log entry with timestamp, level (INFO/WARN/ERROR), and category."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "level": level.upper(),
        "category": category.upper(),
        "message": message.strip(),
    }
    with _LOGS_LOCK:
        _LOG_BUFFER.append(entry)
        try:
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{level.upper()}] [{category.upper()}] {message.strip()}\n")
        except Exception:
            pass


def get_logs(limit: int = 200) -> list[dict[str, str]]:
    """Retrieve recent log entries."""
    with _LOGS_LOCK:
        entries = list(_LOG_BUFFER)
        if limit and limit < len(entries):
            return entries[-limit:]
        return entries


def clear_logs() -> None:
    """Clear memory buffer and truncate the log file."""
    with _LOGS_LOCK:
        _LOG_BUFFER.clear()
        try:
            with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

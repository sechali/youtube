"""SQLite database helpers for storing download history and app configuration."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "history.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and migrate missing columns if needed."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                platform TEXT NOT NULL,
                format_type TEXT NOT NULL,
                resolution TEXT NOT NULL,
                audio_quality TEXT DEFAULT '192',
                file_format TEXT DEFAULT '',
                subtitles TEXT DEFAULT '',
                batch_id TEXT,
                is_playlist INTEGER NOT NULL DEFAULT 0,
                playlist_items TEXT,
                output_dir TEXT,
                task_dir TEXT,
                file_name TEXT,
                file_path TEXT,
                file_size INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(download_history)").fetchall()
        }
        migrations = {
            "audio_quality": "TEXT DEFAULT '192'",
            "file_format": "TEXT DEFAULT ''",
            "subtitles": "TEXT DEFAULT ''",
            "batch_id": "TEXT",
            "playlist_items": "TEXT",
            "output_dir": "TEXT",
            "task_dir": "TEXT",
        }
        for col, col_def in migrations.items():
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE download_history ADD COLUMN {col} {col_def}")
        conn.commit()


def get_setting(key: str, default: str | None = None) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def add_history(entry: dict[str, Any]) -> int:
    """Insert a new download history record and return its row ID."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO download_history (
                url, title, platform, format_type, resolution, audio_quality,
                file_format, subtitles, batch_id,
                is_playlist, playlist_items, output_dir, task_dir,
                file_name, file_path, file_size, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["url"],
                entry["title"],
                entry["platform"],
                entry["format_type"],
                entry["resolution"],
                entry.get("audio_quality", "192"),
                entry.get("file_format", ""),
                entry.get("subtitles", ""),
                entry.get("batch_id"),
                1 if entry.get("is_playlist") else 0,
                entry.get("playlist_items"),
                entry.get("output_dir"),
                entry.get("task_dir"),
                entry.get("file_name"),
                entry.get("file_path"),
                entry.get("file_size", 0),
                entry["status"],
                entry.get("error_message"),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_history(
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    """Return filtered download history records, newest first."""
    query = "SELECT * FROM download_history WHERE 1=1"
    params: list[Any] = []

    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(title) LIKE ? OR LOWER(url) LIKE ?)"
        params.extend([s, s])

    if status and status.lower() not in ("all", "semua"):
        query += " AND LOWER(status) = ?"
        params.append(status.strip().lower())

    if platform and platform.lower() not in ("all", "semua"):
        query += " AND LOWER(platform) = ?"
        params.append(platform.strip().lower())

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_history_stats() -> dict[str, Any]:
    """Calculate aggregate statistics from download history."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM download_history").fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) AS c FROM download_history WHERE status = 'completed'"
        ).fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) AS c FROM download_history WHERE status = 'failed'"
        ).fetchone()["c"]
        total_size = conn.execute(
            "SELECT SUM(file_size) AS s FROM download_history WHERE status = 'completed'"
        ).fetchone()["s"] or 0

        platform_rows = conn.execute(
            "SELECT platform, COUNT(*) as c FROM download_history GROUP BY platform ORDER BY c DESC LIMIT 6"
        ).fetchall()
        platforms = {row["platform"]: row["c"] for row in platform_rows}

    return {
        "total_downloads": total,
        "completed_count": completed,
        "failed_count": failed,
        "total_bytes": total_size,
        "platforms": platforms,
    }


def get_history_item(item_id: int) -> dict[str, Any] | None:
    """Fetch a single history record by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM download_history WHERE id = ?",
            (item_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_history_item(item_id: int) -> bool:
    """Delete a single history record by ID."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM download_history WHERE id = ?", (item_id,))
        conn.commit()
        return cur.rowcount > 0


def clear_history() -> int:
    """Delete all history records and return count deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM download_history")
        conn.commit()
        return cur.rowcount

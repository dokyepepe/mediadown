"""SQLite persistence for downloads and history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.utils.paths import database_path


class HistoryService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    thumbnail TEXT,
                    platform TEXT,
                    media_type TEXT NOT NULL,
                    format TEXT,
                    quality TEXT,
                    output_path TEXT,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    speed REAL,
                    eta INTEGER,
                    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    technical_error TEXT,
                    final_file TEXT,
                    options_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_downloads_created ON downloads(created_at DESC)")

    def upsert(self, item: DownloadItem) -> None:
        values = item.to_dict()
        values["options_json"] = json.dumps(values.pop("options"), ensure_ascii=False)
        columns = list(values)
        placeholders = ", ".join(f":{column}" for column in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        query = (
            f"INSERT INTO downloads ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        with self._lock, self._connect() as connection:
            connection.execute(query, values)

    def list(self, search: str = "", media_type: str = "all", limit: int = 500) -> list[DownloadItem]:
        clauses: list[str] = []
        parameters: list[object] = []
        if search.strip():
            clauses.append("(title LIKE ? OR author LIKE ? OR platform LIKE ?)")
            needle = f"%{search.strip()}%"
            parameters.extend([needle, needle, needle])
        if media_type != "all":
            clauses.append("media_type = ?")
            parameters.append(media_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM downloads {where} ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_item(row) for row in rows]

    def completed(self, search: str = "", media_type: str = "all") -> list[DownloadItem]:
        items = self.list(search, media_type)
        return [item for item in items if item.status == DownloadStatus.COMPLETED]

    def delete(self, item_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM downloads WHERE id = ?", (item_id,))

    def clear_completed(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM downloads WHERE status = ?", (DownloadStatus.COMPLETED.value,))

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> DownloadItem:
        data = dict(row)
        data["options"] = json.loads(data.pop("options_json") or "{}")
        return DownloadItem.from_dict(data)


"""SQLite persistence for downloads and history."""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from io import StringIO
from pathlib import Path
from threading import RLock
from typing import Iterable

from mediadownloader.models import DownloadItem, DownloadStatus
from mediadownloader.utils.paths import database_path

LOGGER = logging.getLogger(__name__)


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
                    file_size INTEGER NOT NULL DEFAULT 0,
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
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        """Add columns introduced after the first release.

        ``CREATE TABLE IF NOT EXISTS`` silently keeps an older layout, so new
        columns are appended explicitly instead of forcing users to delete
        their history.
        """
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(downloads)")}
        if "file_size" not in existing:
            connection.execute("ALTER TABLE downloads ADD COLUMN file_size INTEGER NOT NULL DEFAULT 0")

    def upsert(self, item: DownloadItem) -> None:
        values = item.to_dict()
        values["options_json"] = json.dumps(values.pop("options"), ensure_ascii=False)
        # Queue-only state: history stores finished files, so the provisional
        # batch label never reaches the database.
        values.pop("provisional_title", None)
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

    def delete_many(self, item_ids: Iterable[str]) -> int:
        """Delete several history rows at once; returns how many were removed.

        Rows that are already gone are not an error: the history page can be
        showing a selection that another window just cleared.
        """
        identifiers = [item_id for item_id in dict.fromkeys(item_ids) if item_id]
        if not identifiers:
            return 0
        placeholders = ", ".join("?" for _ in identifiers)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM downloads WHERE id IN ({placeholders})", identifiers
            )
            return int(cursor.rowcount or 0)

    def clear_completed(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM downloads WHERE status = ?", (DownloadStatus.COMPLETED.value,))

    def get(self, item_id: str) -> DownloadItem | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM downloads WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def rename(self, item_id: str, new_name: str) -> str:
        """Rename the downloaded file and point the history row at the new path.

        The stored name is what the history list shows, so it is updated even
        when the file is gone (moved or deleted elsewhere) — matching the mobile
        edition, which only ever renames the row. When the file is still in
        place it is renamed on disk too, so "abrir pasta" keeps working.

        Returns the resulting path. Raises :class:`KeyError` when the row is
        unknown and :class:`FileExistsError` when the destination name is taken,
        so the caller can show a precise message instead of a generic failure.
        """
        item = self.get(item_id)
        if item is None:
            raise KeyError(item_id)
        source = Path(item.final_file or item.output_path or "")
        target = source.with_name(new_name) if str(source) else Path(new_name)
        if target.exists() and target != source:
            raise FileExistsError(str(target))
        if source.is_file() and target != source:
            try:
                source.rename(target)
            except OSError:
                # A locked file must not block the rename of the history row.
                LOGGER.info("Não foi possível renomear %s; apenas o registro foi atualizado.", source)
        item.final_file = str(target)
        self.upsert(item)
        return str(target)

    @staticmethod
    def to_csv(items: list[DownloadItem]) -> str:
        """Render completed downloads as a UTF-8 CSV string (feed and timestamps kept raw)."""
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow([
            "id", "título", "autor", "plataforma", "formato", "qualidade",
            "arquivo", "tamanho_bytes", "criado_em", "concluído_em", "url",
        ])
        for item in items:
            writer.writerow([
                item.id, item.title, item.author, item.platform, item.format, item.quality,
                item.final_file, item.file_size or item.total_bytes or 0, item.created_at,
                item.completed_at or "", item.url,
            ])
        return buffer.getvalue()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> DownloadItem:
        data = dict(row)
        data["options"] = json.loads(data.pop("options_json") or "{}")
        return DownloadItem.from_dict(data)


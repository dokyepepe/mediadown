"""Disk usage statistics and safe cleanup of leftover download temporaries.

Read-only probes live next to the destructive one so the settings page can show
live numbers, but nothing here deletes anything the user asked to keep: only
partial and fragment files that yt-dlp abandoned are ever removed.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mediadownloader.utils.paths import database_path

LOGGER = logging.getLogger(__name__)

#: Suffixes yt-dlp and FFmpeg leave behind when a transfer is interrupted.
TEMPORARY_SUFFIXES = (".part", ".part-Frag", ".ytdl", ".temp", ".tmp")

#: Fragment files are named ``<name>.<ext>.f<fragment index>``; the digits are
#: what distinguishes them from a legitimately named media file.
_FRAGMENT_MARKER = ".f"


@dataclass(frozen=True, slots=True)
class StorageStats:
    """Snapshot of local storage usage, as shown in Settings."""

    completed_count: int = 0
    downloaded_bytes: int = 0
    temporary_bytes: int = 0
    temporary_files: int = 0
    free_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Outcome of a temporary-file sweep."""

    removed_files: int = 0
    freed_bytes: int = 0
    errors: int = 0


def is_temporary_file(path: Path) -> bool:
    """Whether a file is an abandoned download temporary rather than a result.

    Fragment chunks (``video.mp4.f137028``) only count when the trailing part
    after ``.f`` is entirely digits, so a real file such as ``logo.finance.png``
    is never mistaken for one.
    """
    name = path.name
    if any(name.endswith(suffix) for suffix in TEMPORARY_SUFFIXES):
        return True
    marker = name.rfind(_FRAGMENT_MARKER)
    if marker <= 0:
        return False
    tail = name[marker + len(_FRAGMENT_MARKER) :]
    return tail.isdigit()


def _iter_files(roots: Iterable[str | Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        base = Path(root).expanduser()
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            try:
                if path.is_file() and path not in seen:
                    seen.add(path)
                    yield path
            except OSError:
                continue


def temporary_files(roots: Iterable[str | Path]) -> list[Path]:
    """Every leftover temporary under ``roots``, without following symlinks."""
    return [path for path in _iter_files(roots) if is_temporary_file(path)]


def measure_temporaries(roots: Iterable[str | Path]) -> tuple[int, int]:
    """``(total_bytes, file_count)`` of leftover temporaries under ``roots``."""
    total = 0
    count = 0
    for path in temporary_files(roots):
        try:
            total += path.stat().st_size
        except OSError:
            continue
        count += 1
    return total, count


def remove_temporaries(roots: Iterable[str | Path]) -> CleanupResult:
    """Delete leftover temporaries and report how much space was reclaimed."""
    removed = 0
    freed = 0
    errors = 0
    for path in temporary_files(roots):
        try:
            size = path.stat().st_size
            path.unlink()
        except OSError as error:
            LOGGER.info("Não foi possível remover o temporário %s: %s", path, error)
            errors += 1
            continue
        removed += 1
        freed += size
    return CleanupResult(removed, freed, errors)


def _query_totals(path: Path) -> tuple[int, int]:
    """``(completed_count, downloaded_bytes)`` straight from the history table."""
    if not path.is_file():
        return 0, 0
    try:
        with sqlite3.connect(path, timeout=5) as connection:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(downloaded_bytes), 0) "
                "FROM downloads WHERE status = 'completed'"
            ).fetchone()
    except sqlite3.Error as error:
        LOGGER.info("Não foi possível ler as estatísticas do histórico: %s", error)
        return 0, 0
    return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)


def collect(
    download_dirs: Iterable[str | Path],
    *,
    database: Path | None = None,
) -> StorageStats:
    """Gather every number the settings card displays in a single pass.

    A single snapshot keeps the four rows mutually consistent; probing them
    independently could show a free-space number taken before a cleanup.
    """
    directories = [Path(directory).expanduser() for directory in download_dirs]
    completed_count, downloaded_bytes = _query_totals(database or database_path())
    temporary_bytes, temporary_count = measure_temporaries(directories)
    free: int | None = None
    for directory in directories:
        try:
            if not directory.is_dir():
                directory.mkdir(parents=True, exist_ok=True)
            import shutil  # noqa: PLC0415 - only needed when a directory exists

            free = int(shutil.disk_usage(directory).free)
            break
        except OSError:
            continue
    return StorageStats(completed_count, downloaded_bytes, temporary_bytes, temporary_count, free)

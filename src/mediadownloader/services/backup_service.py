"""Export and restore the local configuration as a single portable JSON file.

The payload is intentionally human readable: settings, the per-site cookie
profile list and the contents of every referenced ``cookies.txt`` travel
together, so a user can move their configuration to another machine without
re-picking folders. Secrets that are not user configuration — the Spotify OAuth
session and the yt-dlp rollback state — are deliberately left out, mirroring the
mobile edition.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication

BACKUP_FORMAT = 1
BACKUP_FILENAME = "media_downloader_settings_backup.json"


class BackupError(Exception):
    """Raised when a backup file cannot be read or applied."""


@dataclass(slots=True)
class BackupPayload:
    """A decoded backup, ready to be applied to the services."""

    settings: dict[str, Any] = field(default_factory=dict)
    profiles: list[dict[str, Any]] = field(default_factory=list)
    cookie_files: dict[str, str] = field(default_factory=dict)


def _tr(message: str) -> str:
    return QCoreApplication.translate("BackupService", message)


def cookie_storage_dir() -> Path:
    """Directory holding the copies of every ``cookies.txt`` the app manages."""
    from mediadownloader.utils.paths import app_data_dir  # noqa: PLC0415 - avoids a cycle

    path = app_data_dir() / "cookies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_cookie_path(profile_id: str) -> Path:
    return cookie_storage_dir() / f"{profile_id}.txt"


def _read_cookie(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def export(settings: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the JSON-ready payload for the current configuration.

    Cookie bodies are inlined so the file is self-contained; the absolute paths
    inside each profile are rewritten on import to wherever the new install
    stores its own copies.
    """
    cookies: dict[str, str] = {}
    normalized: list[dict[str, Any]] = []
    for profile in profiles:
        if not isinstance(profile, dict) or not profile.get("id"):
            continue
        entry = {
            "id": str(profile["id"]),
            "label": str(profile.get("label") or ""),
            "hosts": [str(host) for host in (profile.get("hosts") or [])],
        }
        if profile.get("impersonate"):
            entry["impersonate"] = str(profile["impersonate"])
        normalized.append(entry)
        source = Path(str(profile.get("file") or "")).expanduser()
        if source.is_file():
            cookies[entry["id"]] = _read_cookie(source)
    return {
        "format": BACKUP_FORMAT,
        "application": "MediaDownloader",
        "settings": settings,
        "cookie_profiles": normalized,
        "cookie_files": cookies,
    }


def dumps(settings: dict[str, Any], profiles: list[dict[str, Any]]) -> str:
    """Serialize :func:`export` output as indented JSON."""
    return json.dumps(export(settings, profiles), ensure_ascii=False, indent=2)


def loads(raw: str) -> BackupPayload:
    """Parse and validate a backup document.

    Raises :class:`BackupError` instead of letting ``JSONDecodeError`` escape so
    the UI can show one consistent message for every malformed input.
    """
    try:
        document = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise BackupError(_tr("O arquivo selecionado não é um backup válido.")) from error
    if not isinstance(document, dict):
        raise BackupError(_tr("O arquivo selecionado não é um backup válido."))
    version = document.get("format")
    if version != BACKUP_FORMAT:
        raise BackupError(
            _tr("Este backup foi criado por outra versão do aplicativo e não pode ser lido.")
        )
    settings = document.get("settings")
    profiles = document.get("cookie_profiles") or []
    cookies = document.get("cookie_files") or {}
    if not isinstance(settings, dict):
        raise BackupError(_tr("O backup não contém configurações reconhecíveis."))
    if not isinstance(profiles, list) or not isinstance(cookies, dict):
        raise BackupError(_tr("O backup não contém perfis de cookies válidos."))
    return BackupPayload(
        settings={key: value for key, value in settings.items()},
        profiles=[profile for profile in profiles if isinstance(profile, dict)],
        cookie_files={
            str(key): value for key, value in cookies.items() if isinstance(value, str)
        },
    )


def apply(payload: BackupPayload) -> list[dict[str, Any]]:
    """Write the backup's cookie files to disk and return rewritten profiles.

    Profiles end up pointing at the copies inside this install's data
    directory, so a restore keeps working even if the original profile lived on
    a drive that is no longer present.
    """
    restored: list[dict[str, Any]] = []
    for profile in payload.profiles:
        profile_id = str(profile.get("id") or "").strip()
        if not profile_id:
            continue
        body = payload.cookie_files.get(profile_id, "")
        destination = profile_cookie_path(profile_id)
        if body:
            destination.write_text(body, encoding="utf-8")
        elif destination.exists():
            destination.unlink()
        entry: dict[str, Any] = {
            "id": profile_id,
            "label": str(profile.get("label") or ""),
            "hosts": [str(host) for host in (profile.get("hosts") or [])],
            "file": str(destination),
        }
        if profile.get("impersonate"):
            entry["impersonate"] = str(profile["impersonate"])
        restored.append(entry)
    return restored

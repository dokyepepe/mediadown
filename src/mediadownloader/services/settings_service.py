"""Atomic, local-only application settings."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

from mediadownloader.utils.paths import default_download_dir, settings_path


DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {
        "language": "pt_BR",
        "theme": "system",
        "download_dir": str(default_download_dir()),
        "open_folder_on_complete": False,
        "notifications": True,
        "confirm_close_active": True,
        "first_run": True,
    },
    "storage": {
        "video_dir": str(default_download_dir()),
        "audio_dir": str(default_download_dir()),
        "site_files_dir": str(default_download_dir()),
    },
    "downloads": {
        "concurrent": 2,
        "video_format": "auto",
        "video_quality": "auto",
        "audio_format": "mp3",
        "audio_quality": "192",
        "embed_thumbnail": True,
        "add_metadata": True,
        "duplicate_policy": "rename",
        "create_playlist_folder": True,
    },
    "filenames": {"template": "%(title)s.%(ext)s"},
    "network": {"proxy_type": "none", "proxy_url": ""},
    "cookies": {"source": "none", "file": "", "browser": ""},
    "spotify": {"client_id": ""},
}


class SettingsService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self._lock = RLock()
        self._data = deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise TypeError("settings root must be an object")
                self._merge(self._data, loaded)
                # Before per-type destinations existed, every download used
                # general.download_dir. Preserve that choice during migration.
                loaded_storage = loaded.get("storage", {})
                loaded_general = loaded.get("general", {})
                legacy_directory = (
                    loaded_general.get("download_dir")
                    if isinstance(loaded_general, dict)
                    else None
                )
                if isinstance(loaded_storage, dict) and isinstance(legacy_directory, str):
                    target_storage = self._data.get("storage")
                    if not isinstance(target_storage, dict):
                        raise TypeError("storage settings must be an object")
                    for key in ("video_dir", "audio_dir", "site_files_dir"):
                        if key not in loaded_storage:
                            target_storage[key] = legacy_directory
            except (OSError, json.JSONDecodeError, TypeError):
                backup = self.path.with_suffix(".invalid.json")
                try:
                    self.path.replace(backup)
                except OSError:
                    pass

    @staticmethod
    def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                SettingsService._merge(target[key], value)
            else:
                target[key] = value

    def get(self, dotted_key: str, default: Any = None) -> Any:
        value: Any = self._data
        for key in dotted_key.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return deepcopy(value)

    def set(self, dotted_key: str, value: Any, save: bool = True) -> None:
        with self._lock:
            target = self._data
            parts = dotted_key.split(".")
            for key in parts[:-1]:
                target = target.setdefault(key, {})
            target[parts[-1]] = value
            if save:
                self.save()

    def update_section(self, section: str, values: dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault(section, {}).update(values)
            self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temporary, self.path)

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

"""Filesystem locations for development and frozen builds."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

from mediadownloader.version import APP_ID, ORGANIZATION_NAME


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return project_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath("resources", *parts)


def asset_path(*parts: str) -> Path:
    return bundle_root().joinpath("assets", *parts)


def app_data_dir() -> Path:
    override = os.environ.get("MEDIA_DOWNLOADER_DATA_DIR", "").strip()
    path = (
        Path(override).expanduser().resolve()
        if override
        else Path(user_data_dir(APP_ID, ORGANIZATION_NAME, roaming=False))
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = Path(user_log_dir(APP_ID, ORGANIZATION_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def database_path() -> Path:
    return app_data_dir() / "history.sqlite3"


def components_dir() -> Path:
    path = app_data_dir() / "components"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    candidate = Path.home() / "Downloads"
    return candidate if candidate.exists() else Path.home()


def reveal_in_explorer(path: str | Path, select_file: bool = False) -> None:
    target = Path(path).resolve()
    if sys.platform == "win32" and select_file and target.is_file():
        os.startfile("explorer.exe", arguments=f'/select,"{target}"')  # type: ignore[attr-defined]
    elif sys.platform == "win32":
        directory = target if target.is_dir() else target.parent
        os.startfile(str(directory))  # type: ignore[attr-defined]
    else:
        destination = target if target.exists() and not select_file else target.parent
        command = ["open" if sys.platform == "darwin" else "xdg-open", str(destination)]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_local_file(path: str | Path) -> None:
    """Open a local file with the platform default application."""
    target = Path(path).resolve()
    if sys.platform == "win32":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    command = ["open" if sys.platform == "darwin" else "xdg-open", str(target)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


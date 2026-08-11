"""Controlled yt-dlp package update stored in the user's component directory."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from mediadownloader.utils.paths import components_dir

LOGGER = logging.getLogger(__name__)
PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"


class UpdateService:
    def current_ytdlp_version(self) -> str:
        try:
            from yt_dlp.version import __version__
            return __version__
        except Exception:
            try:
                return importlib.metadata.version("yt-dlp")
            except importlib.metadata.PackageNotFoundError:
                return "não instalado"

    def latest_ytdlp_version(self, timeout: int = 15) -> str:
        with urllib.request.urlopen(PYPI_URL, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
            payload = json.load(response)
        return str(payload["info"]["version"])

    def update_ytdlp(self, timeout: int = 60) -> str:
        """Download a verified wheel; it becomes active after restarting the app."""
        with urllib.request.urlopen(PYPI_URL, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
        version = str(payload["info"]["version"])
        wheel = next(
            file for file in payload["urls"]
            if file["packagetype"] == "bdist_wheel" and file["filename"].endswith("py3-none-any.whl")
        )
        target = components_dir() / "yt-dlp"
        with tempfile.TemporaryDirectory(prefix="media-downloader-update-") as temporary:
            archive = Path(temporary) / wheel["filename"]
            request = urllib.request.Request(wheel["url"], headers={"User-Agent": "MediaDownloader/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response, archive.open("wb") as output:  # noqa: S310
                shutil.copyfileobj(response, output)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            if digest.lower() != wheel["digests"]["sha256"].lower():
                raise ValueError("Falha na verificação SHA-256 do pacote yt-dlp.")
            staged = Path(temporary) / "extracted"
            with zipfile.ZipFile(archive) as package:
                package.extractall(staged)
            replacement = target.with_name("yt-dlp-new")
            if replacement.exists():
                shutil.rmtree(replacement)
            shutil.copytree(staged, replacement)
            old = target.with_name("yt-dlp-old")
            if old.exists():
                shutil.rmtree(old)
            if target.exists():
                target.replace(old)
            replacement.replace(target)
            if old.exists():
                shutil.rmtree(old, ignore_errors=True)
        return version


def activate_updated_ytdlp() -> None:
    target = components_dir() / "yt-dlp"
    if target.exists() and str(target) not in sys.path:
        sys.path.insert(0, str(target))


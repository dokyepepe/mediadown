"""Locate and inspect bundled FFmpeg without relying on PATH in production."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from mediadownloader.utils.paths import resource_path


class FFmpegManager:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or resource_path("ffmpeg")

    @property
    def ffmpeg(self) -> Path | None:
        for name in ("ffmpeg.exe", "ffmpeg"):
            bundled = self.directory / name
            if bundled.exists():
                return bundled
        found = shutil.which("ffmpeg")
        return Path(found) if found else None

    @property
    def ffprobe(self) -> Path | None:
        for name in ("ffprobe.exe", "ffprobe"):
            bundled = self.directory / name
            if bundled.exists():
                return bundled
        found = shutil.which("ffprobe")
        return Path(found) if found else None

    @property
    def available(self) -> bool:
        return self.ffmpeg is not None and self.ffprobe is not None

    def location(self) -> str:
        executable = self.ffmpeg
        return str(executable.parent) if executable else ""

    def version(self) -> str:
        executable = self.ffmpeg
        if not executable:
            return "não instalado"
        try:
            completed = subprocess.run(
                [str(executable), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            first_line = completed.stdout.splitlines()[0]
            return first_line.replace("ffmpeg version ", "").split(" ", 1)[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            return "desconhecida"


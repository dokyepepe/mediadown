"""Locate and inspect bundled FFmpeg without relying on PATH in production."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from mediadownloader.utils.paths import resource_path


def _normalize_input_url(source_url: str) -> str:
    """Convert file:// URL to a plain path for FFmpeg (which does not resolve it)."""
    if not source_url.startswith("file://"):
        return source_url
    try:
        parsed = urlparse(source_url)
        path = url2pathname(unquote(parsed.path))
        if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = str(Path(path[1:]))
        return path
    except (ValueError, OSError):
        return source_url


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

    def render_preview(
        self,
        source_url: str,
        output_path: Path,
        audio_filter: str,
        duration: float = 12.0,
        start_time: float = 0.0,
        timeout: float = 90.0,
    ) -> Path:
        """Render a short preview clip with the given `-af` filter graph.

        ``start_time`` (seconds) seeks the input before decoding, so the clip
        is taken from the segment the user is listening to (near real-time).
        First tries to keep the video stream untouched (fast); if the source
        cannot be remuxed with its native codec, falls back to an ultrafast
        x264 re-encode. Raises on failure so callers can degrade gracefully.
        """
        executable = self.ffmpeg
        if not executable:
            raise RuntimeError("FFmpeg não está disponível para a pré-visualização.")
        start_time = max(0.0, float(start_time))
        source_url = _normalize_input_url(source_url)
        attempts = (
            [
                str(executable), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start_time:.3f}",
                "-i", source_url, "-t", str(duration),
                "-sn", "-dn",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-af", audio_filter,
                "-f", "matroska", str(output_path),
            ],
            [
                str(executable), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start_time:.3f}",
                "-i", source_url, "-t", str(duration),
                "-sn", "-dn",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "160k",
                "-af", audio_filter,
                "-f", "matroska", str(output_path),
            ],
            # Audio-only fallback (also covers sources whose video cannot be
            # remuxed/re-encoded): keep the sound, never fail a preview over video.
            [
                str(executable), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start_time:.3f}",
                "-i", source_url, "-t", str(duration),
                "-vn",
                "-c:a", "aac", "-b:a", "160k",
                "-af", audio_filter,
                "-f", "matroska", str(output_path),
            ],
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        last_error = ""
        for arguments in attempts:
            try:
                completed = subprocess.run(
                    arguments,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                    creationflags=flags,
                )
            except subprocess.SubprocessError as error:
                last_error = str(error)
                continue
            if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            stderr_tail = (completed.stderr or b"").decode("utf-8", "replace")[-400:]
            last_error = f"ffmpeg retornou {completed.returncode}: {stderr_tail}"
        raise RuntimeError(last_error or "Falha ao gerar a pré-visualização.")


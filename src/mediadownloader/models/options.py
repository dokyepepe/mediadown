"""User-selected download options."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .download_item import MediaType


@dataclass(slots=True)
class DownloadOptions:
    media_type: MediaType = MediaType.VIDEO
    video_format: str = "auto"
    video_quality: str = "auto"
    audio_format: str = "mp3"
    audio_quality: str = "192"
    embed_thumbnail: bool = True
    add_metadata: bool = True
    subtitle_mode: str = "none"
    subtitle_language: str = "auto"
    all_subtitles: bool = False
    audio_speed: float = 1.0
    audio_pitch: float = 1.0
    audio_volume: float = 1.0
    audio_bass: bool = False
    audio_echo: bool = False
    audio_tremolo: bool = False
    audio_normalize: bool = False
    output_dir: str = ""
    filename_template: str = "%(title)s.%(ext)s"
    create_playlist_folder: bool = True
    duplicate_policy: str = "rename"
    proxy: str = ""
    cookies_file: str = ""
    cookies_browser: str = ""
    impersonate: str = ""
    rate_limit_kbps: int = 0
    trim_start_seconds: float = 0.0
    trim_duration_seconds: float = 0.0
    fade_in_seconds: float = 0.0
    fade_out_seconds: float = 0.0
    editor_compatible: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["media_type"] = self.media_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadOptions":
        values = dict(data)
        values["media_type"] = MediaType(values.get("media_type", MediaType.VIDEO))
        return cls(**values)

    @property
    def needs_post_processing(self) -> bool:
        """True when FFmpeg has to run after the download to honour the selection."""
        return bool(
            self.trim_duration_seconds
            or self.fade_in_seconds
            or self.fade_out_seconds
            or self.editor_compatible
        )


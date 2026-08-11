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
    output_dir: str = ""
    filename_template: str = "%(title)s.%(ext)s"
    create_playlist_folder: bool = True
    duplicate_policy: str = "rename"
    proxy: str = ""
    cookies_file: str = ""
    cookies_browser: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["media_type"] = self.media_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadOptions":
        values = dict(data)
        values["media_type"] = MediaType(values.get("media_type", MediaType.VIDEO))
        return cls(**values)


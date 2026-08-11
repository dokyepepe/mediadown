"""Normalized metadata returned by the extractor."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class MediaFormat:
    format_id: str
    extension: str
    resolution: str
    height: int | None = None
    width: int | None = None
    fps: float | None = None
    video_codec: str = ""
    audio_codec: str = ""
    filesize: int | None = None
    dynamic_range: str = ""


@dataclass(slots=True, frozen=True)
class PlaylistEntry:
    url: str
    title: str
    index: int
    thumbnail: str = ""
    duration: int | None = None
    author: str = ""
    album: str = ""
    resource_type: str = "media"


@dataclass(slots=True)
class MediaInfo:
    url: str
    title: str
    author: str = ""
    thumbnail: str = ""
    duration: int | None = None
    platform: str = ""
    media_id: str = ""
    webpage_url: str = ""
    formats: list[MediaFormat] = field(default_factory=list)
    subtitles: dict[str, list[dict]] = field(default_factory=dict)
    automatic_captions: dict[str, list[dict]] = field(default_factory=dict)
    is_playlist: bool = False
    playlist_count: int = 0
    entries: list[PlaylistEntry] = field(default_factory=list)
    download_supported: bool = True
    source_notice: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def available_heights(self) -> list[int]:
        return sorted({item.height for item in self.formats if item.height}, reverse=True)

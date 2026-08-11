"""Translate normalized UI choices into yt-dlp format selectors."""

from __future__ import annotations

from mediadownloader.models import DownloadOptions, MediaType


class FormatManager:
    VIDEO_CONTAINERS = {"auto", "mp4", "mkv", "webm"}
    AUDIO_FORMATS = {"mp3", "m4a", "aac", "opus", "flac", "wav"}

    @classmethod
    def selector(cls, options: DownloadOptions) -> str:
        if options.media_type == MediaType.AUDIO:
            return "bestaudio/best"
        height = cls._height(options.video_quality)
        limit = f"[height<={height}]" if height else ""
        container = options.video_format.lower()
        if container == "mp4":
            # Prefer native MP4/M4A, then allow yt-dlp/FFmpeg to remux compatible streams.
            return (
                f"bestvideo{limit}[ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo{limit}+bestaudio/best{limit}"
            )
        if container == "webm":
            return (
                f"bestvideo{limit}[ext=webm]+bestaudio[ext=webm]/"
                f"bestvideo{limit}+bestaudio/best{limit}"
            )
        return f"bestvideo{limit}+bestaudio/best{limit}"

    @staticmethod
    def _height(quality: str) -> int | None:
        digits = "".join(character for character in quality if character.isdigit())
        return int(digits) if digits else None

    @classmethod
    def postprocessors(cls, options: DownloadOptions) -> list[dict]:
        processors: list[dict] = []
        if options.media_type == MediaType.AUDIO:
            codec = options.audio_format.lower()
            processors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": options.audio_quality if codec == "mp3" else "0",
            })
        if options.add_metadata:
            processors.append({"key": "FFmpegMetadata", "add_metadata": True})
        if options.embed_thumbnail:
            processors.append({"key": "EmbedThumbnail"})
        if options.subtitle_mode == "embed" and options.media_type == MediaType.VIDEO:
            processors.append({"key": "FFmpegEmbedSubtitle"})
        return processors


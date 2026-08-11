"""Thread-agnostic yt-dlp wrapper. The UI never imports yt-dlp directly."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

import yt_dlp
from yt_dlp.utils import DownloadError

from mediadownloader.models import (
    DownloadItem,
    DownloadOptions,
    DownloadStatus,
    MediaFormat,
    MediaInfo,
    MediaType,
    PlaylistEntry,
)
from mediadownloader.utils.errors import FriendlyError, classify_error
from mediadownloader.utils.filenames import unique_path, validate_template
from mediadownloader.utils.paths import resource_path
from mediadownloader.utils.validators import is_spotify_url

from .ffmpeg_manager import FFmpegManager
from .format_manager import FormatManager

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]


class DownloadCancelled(Exception):
    pass


class _YtdlpLogger:
    def debug(self, message: str) -> None:
        LOGGER.debug(message)

    def warning(self, message: str) -> None:
        LOGGER.warning(message)

    def error(self, message: str) -> None:
        LOGGER.error(message)


class DownloadEngine:
    def __init__(self, ffmpeg: FFmpegManager | None = None) -> None:
        self.ffmpeg = ffmpeg or FFmpegManager()

    def analyze(
        self,
        url: str,
        proxy: str = "",
        cookies_file: str = "",
        cookies_browser: str = "",
    ) -> MediaInfo:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "logger": _YtdlpLogger(),
            "socket_timeout": 20,
        }
        options.update(self._component_options())
        if proxy:
            options["proxy"] = proxy
        if cookies_file:
            options["cookiefile"] = cookies_file
        elif cookies_browser:
            options["cookiesfrombrowser"] = (cookies_browser,)
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                raise FriendlyError("Não foi possível obter informações desta mídia.")
            return self._normalize(url, info)
        except FriendlyError:
            raise
        except Exception as error:
            LOGGER.exception("Falha ao analisar URL")
            raise classify_error(error) from error

    def _normalize(self, requested_url: str, info: dict[str, Any]) -> MediaInfo:
        entries_raw = [entry for entry in (info.get("entries") or []) if entry]
        is_playlist = info.get("_type") in {"playlist", "multi_video"} or bool(entries_raw)
        entries = [
            PlaylistEntry(
                url=str(entry.get("webpage_url") or entry.get("url") or ""),
                title=str(entry.get("title") or f"Item {index}"),
                index=index,
                thumbnail=str(entry.get("thumbnail") or ""),
                duration=entry.get("duration"),
            )
            for index, entry in enumerate(entries_raw, start=1)
            if entry.get("url") or entry.get("webpage_url")
        ]
        formats = [
            MediaFormat(
                format_id=str(item.get("format_id") or ""),
                extension=str(item.get("ext") or ""),
                resolution=str(item.get("resolution") or item.get("format_note") or ""),
                height=item.get("height"),
                width=item.get("width"),
                fps=item.get("fps"),
                video_codec=str(item.get("vcodec") or ""),
                audio_codec=str(item.get("acodec") or ""),
                filesize=item.get("filesize") or item.get("filesize_approx"),
                dynamic_range=str(item.get("dynamic_range") or ""),
            )
            for item in (info.get("formats") or [])
        ]
        thumbnails = info.get("thumbnails") or []
        thumbnail = info.get("thumbnail") or (thumbnails[-1].get("url", "") if thumbnails else "")
        return MediaInfo(
            url=requested_url,
            title=str(info.get("title") or info.get("playlist_title") or "Mídia sem título"),
            author=str(info.get("uploader") or info.get("channel") or info.get("creator") or ""),
            thumbnail=str(thumbnail or ""),
            duration=info.get("duration"),
            platform=str(info.get("extractor_key") or info.get("extractor") or "").replace("Playlist", ""),
            media_id=str(info.get("id") or ""),
            webpage_url=str(info.get("webpage_url") or requested_url),
            formats=formats,
            subtitles=info.get("subtitles") or {},
            automatic_captions=info.get("automatic_captions") or {},
            is_playlist=is_playlist,
            playlist_count=int(info.get("playlist_count") or len(entries)),
            entries=entries,
            raw=info,
        )

    def download(
        self,
        item: DownloadItem,
        options: DownloadOptions,
        progress: ProgressCallback,
        cancel_event: threading.Event,
    ) -> str:
        if is_spotify_url(item.url):
            raise FriendlyError(
                "O Spotify está disponível apenas para metadados e playlists. "
                "O aplicativo não baixa nem converte áudio do Spotify.",
                code="spotify_download_unsupported",
            )
        valid_template, template_error = validate_template(options.filename_template)
        if not valid_template:
            raise FriendlyError(template_error, code="template")
        output_dir = Path(options.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if not output_dir.is_dir():
            raise FriendlyError("A pasta de destino não é válida.", code="output")
        if not self.ffmpeg.available and self._needs_ffmpeg(options):
            raise FriendlyError(
                "O FFmpeg não foi encontrado. Execute o script de configuração dos componentes.",
                code="ffmpeg_missing",
            )

        final_filename: list[str] = []

        def progress_hook(data: dict[str, Any]) -> None:
            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelado pelo usuário.")
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = int(data.get("downloaded_bytes") or 0)
                percent = min(99.0, downloaded * 100 / total) if total else 0.0
                stream = data.get("info_dict") or {}
                if stream.get("vcodec") not in {None, "none"} and stream.get("acodec") in {None, "none"}:
                    download_status = DownloadStatus.DOWNLOADING_VIDEO
                elif stream.get("vcodec") in {None, "none"}:
                    download_status = DownloadStatus.DOWNLOADING_AUDIO
                else:
                    download_status = DownloadStatus.DOWNLOADING
                progress({
                    "status": download_status.value,
                    "progress": percent,
                    "speed": data.get("speed"),
                    "eta": data.get("eta"),
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                })
            elif status == "finished":
                filename = data.get("filename")
                if filename:
                    final_filename[:] = [str(filename)]
                progress({
                    "status": DownloadStatus.FINALIZING.value,
                    "progress": 99.0,
                    "eta": None,
                    "speed": None,
                })

        def postprocessor_hook(data: dict[str, Any]) -> None:
            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelado pelo usuário.")
            name = str(data.get("postprocessor") or "").lower()
            if "extractaudio" in name:
                status = DownloadStatus.CONVERTING
            elif "merger" in name:
                status = DownloadStatus.MERGING
            else:
                status = DownloadStatus.FINALIZING
            progress({"status": status.value, "progress": 99.0, "eta": None, "speed": None})

        ydl_options: dict[str, Any] = {
            "format": FormatManager.selector(options),
            "outtmpl": str(output_dir / options.filename_template),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "postprocessors": FormatManager.postprocessors(options),
            "logger": _YtdlpLogger(),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "continuedl": True,
            "overwrites": options.duplicate_policy == "overwrite",
            "writethumbnail": options.embed_thumbnail,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "socket_timeout": 30,
        }
        ydl_options.update(self._component_options())
        if options.video_format in {"mp4", "mkv", "webm"} and options.media_type == MediaType.VIDEO:
            ydl_options["merge_output_format"] = options.video_format
        if self.ffmpeg.available:
            ydl_options["ffmpeg_location"] = self.ffmpeg.location()
        if options.proxy:
            ydl_options["proxy"] = options.proxy
        if options.cookies_file:
            ydl_options["cookiefile"] = options.cookies_file
        elif options.cookies_browser:
            ydl_options["cookiesfrombrowser"] = (options.cookies_browser,)
        if options.subtitle_mode != "none":
            ydl_options["writesubtitles"] = True
            ydl_options["writeautomaticsub"] = True
            ydl_options["subtitleslangs"] = [options.subtitle_language] if options.subtitle_language != "auto" else ["all"]
            ydl_options["embedsubtitles"] = options.subtitle_mode == "embed"

        if options.duplicate_policy in {"rename", "skip"}:
            existing = self._prepare_collision_policy(item.url, ydl_options, options)
            if existing:
                progress({"status": DownloadStatus.FINALIZING.value, "progress": 99.0})
                return existing

        try:
            progress({"status": DownloadStatus.PREPARING.value, "progress": 0.0})
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                result = ydl.extract_info(item.url, download=True)
                if result:
                    prepared = ydl.prepare_filename(result)
                    final_filename[:] = [str(prepared)]
                    requested = result.get("requested_downloads") or []
                    if requested and requested[-1].get("filepath"):
                        final_filename[:] = [str(requested[-1]["filepath"])]
            if cancel_event.is_set():
                raise DownloadCancelled()
            return self._locate_final_file(final_filename[-1] if final_filename else "", options)
        except DownloadCancelled:
            raise
        except DownloadError as error:
            if cancel_event.is_set():
                raise DownloadCancelled() from error
            LOGGER.exception("yt-dlp falhou no download %s", item.id)
            raise classify_error(error) from error
        except FriendlyError:
            raise
        except Exception as error:
            if cancel_event.is_set():
                raise DownloadCancelled() from error
            LOGGER.exception("Falha no download %s", item.id)
            raise classify_error(error) from error

    @staticmethod
    def _needs_ffmpeg(options: DownloadOptions) -> bool:
        return (
            options.media_type == MediaType.AUDIO
            or options.video_format != "auto"
            or options.embed_thumbnail
            or options.add_metadata
            or options.subtitle_mode == "embed"
        )

    def _component_options(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.ffmpeg.available:
            result["ffmpeg_location"] = self.ffmpeg.location()
        deno = resource_path("deno", "deno.exe")
        if deno.exists():
            result["js_runtimes"] = {"deno": {"path": str(deno)}}
        return result

    @staticmethod
    def _prepare_collision_policy(
        url: str,
        ydl_options: dict[str, Any],
        options: DownloadOptions,
    ) -> str:
        """Resolve the post-processed path before download and avoid overwrites."""
        probe_options = dict(ydl_options)
        probe_options.update({"skip_download": True, "writethumbnail": False, "postprocessors": []})
        probe_options.pop("progress_hooks", None)
        probe_options.pop("postprocessor_hooks", None)
        with yt_dlp.YoutubeDL(probe_options) as probe:
            info = probe.extract_info(url, download=False)
            if not info:
                return ""
            prepared = Path(probe.prepare_filename(info))
        final_extension = (
            options.audio_format
            if options.media_type == MediaType.AUDIO
            else options.video_format
            if options.video_format != "auto"
            else prepared.suffix.lstrip(".")
        )
        final_path = prepared.with_suffix(f".{final_extension}")
        if not final_path.exists():
            return ""
        if options.duplicate_policy == "skip":
            return str(final_path)
        renamed = unique_path(final_path)
        ydl_options["outtmpl"] = str(renamed.with_suffix(".%(ext)s"))
        return ""

    @staticmethod
    def _locate_final_file(prepared: str, options: DownloadOptions) -> str:
        candidate = Path(prepared)
        if options.media_type == MediaType.AUDIO:
            converted = candidate.with_suffix(f".{options.audio_format}")
            if converted.exists():
                return str(converted)
        if options.video_format != "auto":
            merged = candidate.with_suffix(f".{options.video_format}")
            if merged.exists():
                return str(merged)
        return str(candidate)

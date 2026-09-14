"""Thread-agnostic yt-dlp wrapper. The UI never imports yt-dlp directly."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

import yt_dlp
import yt_dlp.cookies as yt_cookies
from yt_dlp.utils import DownloadError

from mediadownloader.models import (
    CookieCheck,
    DownloadItem,
    DownloadOptions,
    DownloadStatus,
    MediaFormat,
    MediaInfo,
    MediaType,
    PlaylistEntry,
    PreviewSource,
)
from mediadownloader.utils.errors import FriendlyError, classify_error
from mediadownloader.utils.filenames import unique_path, validate_template
from mediadownloader.utils.paths import resource_path
from mediadownloader.utils.validators import is_spotify_url

from .ffmpeg_manager import FFmpegManager
from .format_manager import FormatManager

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]

_SESSION_COOKIE_NAMES = frozenset({"SID", "SAPISID", "__Secure-3PAPISID", "LOGIN_INFO"})


class DownloadCancelled(Exception):
    pass


class _ProgressReporter:
    """Bound progress events so long downloads cannot flood Qt's event queue."""

    MIN_INTERVAL_SECONDS = 0.25
    MIN_PERCENT_STEP = 0.5

    def __init__(
        self,
        callback: ProgressCallback,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._callback = callback
        self._clock = clock
        self._last_time = float("-inf")
        self._last_progress = -1.0
        self._last_status = ""

    def emit(self, update: dict[str, Any], *, force: bool = False) -> bool:
        now = self._clock()
        status = str(update.get("status") or "")
        value = float(update.get("progress") or 0.0)
        should_emit = (
            force
            or status != self._last_status
            or now - self._last_time >= self.MIN_INTERVAL_SECONDS
            or value - self._last_progress >= self.MIN_PERCENT_STEP
        )
        if not should_emit:
            return False
        self._callback(update)
        self._last_time = now
        self._last_progress = value
        self._last_status = status
        return True


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
                author=str(
                    entry.get("uploader")
                    or entry.get("channel")
                    or entry.get("artist")
                    or ""
                ),
                album=str(entry.get("album") or ""),
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
            # The normalized fields above are all the regular UI needs. Keeping the
            # complete yt-dlp response here duplicated format/playlist metadata and
            # could retain hundreds of MB after analyzing very large playlists.
            raw={},
        )

    def preview_source(
        self,
        url: str,
        proxy: str = "",
        cookies_file: str = "",
        cookies_browser: str = "",
    ) -> PreviewSource:
        """Resolve a directly playable stream for the in-app preview.

        Prefers a single muxed format (video+audio), then audio-only or
        video-only. Sites that only expose separate DASH tracks will preview
        without one of the streams; the UI warns instead of failing hard.
        """
        selectors = (
            "best[acodec!=none][vcodec!=none]",
            "best[acodec!=none]",
            "best[vcodec!=none]",
            "best",
        )
        last_error: Exception | None = None
        for selector in selectors:
            try:
                info = self._extract_single(url, selector, proxy, cookies_file, cookies_browser)
            except Exception as error:  # noqa: BLE001 - probe each fallback selector
                last_error = error
                continue
            direct = info.get("url")
            if not direct:
                continue
            return PreviewSource(
                url=str(direct),
                extension=str(info.get("ext") or ""),
                duration=info.get("duration"),
                has_video=info.get("vcodec") not in (None, "none"),
                has_audio=info.get("acodec") not in (None, "none"),
            )
        if last_error is not None:
            LOGGER.warning("Pré-visualização indisponível: %s", last_error)
        raise FriendlyError(
            "Não foi possível preparar a pré-visualização desta mídia. "
            "Você ainda pode baixá-la normalmente.",
            code="preview_unavailable",
        )

    def _extract_single(
        self,
        url: str,
        selector: str,
        proxy: str,
        cookies_file: str,
        cookies_browser: str,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "format": selector,
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
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise FriendlyError("Não foi possível obter informações desta mídia.")
        return info

    def check_cookies(self, source: str = "none", file: str = "", browser: str = "") -> CookieCheck:
        """Validate the configured cookie source and report diagnostics."""
        if source == "file":
            return self._check_cookie_file(file)
        if source == "browser":
            return self._check_cookie_browser(browser)
        return CookieCheck(
            True,
            "Nenhuma fonte de cookies ativa. Conteúdo que exige login "
            "(vídeo privado, restrições por idade) pode ficar bloqueado.",
        )

    def _cookie_report(self, jar, label: str) -> CookieCheck:
        count = len(jar)
        names = {cookie.name for cookie in jar}
        logged = bool(names & _SESSION_COOKIE_NAMES)
        if logged:
            return CookieCheck(
                True,
                f"Cookies carregados ({label}): {count} cookies com sessão do YouTube reconhecida.",
                "",
                count,
                True,
            )
        if count:
            return CookieCheck(
                True,
                f"Cookies carregados ({label}): {count} cookies.",
                "",
                count,
                False,
            )
        return CookieCheck(
            False,
            f"A fonte de cookies ({label}) não forneceu cookies. "
            "Pode estar sem sessão ativa ou desatualizada.",
        )

    def _check_cookie_file(self, path: str) -> CookieCheck:
        if not path:
            return CookieCheck(False, "Escolha um arquivo cookies.txt para usar esta fonte.")
        cookie_path = Path(path).expanduser()
        if not cookie_path.is_file():
            return CookieCheck(False, "Arquivo cookies.txt não encontrado.", str(cookie_path))
        try:
            jar = yt_cookies.load_cookies(cookie_path, None, None)
        except Exception as error:  # noqa: BLE001 - yt-dlp raises mixed types here
            LOGGER.warning("Falha ao carregar cookies de arquivo: %s", error)
            return CookieCheck(
                False,
                "O arquivo cookies.txt não pôde ser lido. "
                "Verifique se está no formato Netscape.",
                str(error),
            )
        return self._cookie_report(jar, cookie_path.name)

    def _check_cookie_browser(self, browser: str) -> CookieCheck:
        if browser not in yt_cookies.SUPPORTED_BROWSERS:
            return CookieCheck(False, "Navegador não suportado pelo yt-dlp.", browser)
        try:
            jar = yt_cookies.extract_cookies_from_browser(browser)
        except (yt_cookies.CookieLoadError, OSError) as error:
            return self._browser_cookie_failure(browser, str(error))
        except Exception as error:  # noqa: BLE001 - profile/keyring issues are site-specific
            LOGGER.warning("Falha ao extrair cookies do %s: %s", browser, error)
            return CookieCheck(
                False,
                f"Não foi possível ler os cookies do {browser}.",
                str(error),
            )
        return self._cookie_report(jar, browser)

    def _browser_cookie_failure(self, browser: str, detail: str) -> CookieCheck:
        text = detail.lower()
        if "could not find" in text or ("database" in text and "find" in text):
            return CookieCheck(
                False,
                f"Nenhum perfil do {browser} foi encontrado neste computador.",
                detail,
            )
        if "locked" in text or "should close" in text or "does not support" in text:
            return CookieCheck(
                False,
                f"Não foi possível acessar os cookies do {browser}. "
                "Feche o navegador e tente novamente.",
                detail,
            )
        return CookieCheck(False, f"Não foi possível acessar os cookies do {browser}.", detail)

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
        reporter = _ProgressReporter(progress)

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
                reporter.emit({
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
                reporter.emit({
                    "status": DownloadStatus.FINALIZING.value,
                    "progress": 99.0,
                    "eta": None,
                    "speed": None,
                }, force=True)

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
            reporter.emit(
                {"status": status.value, "progress": 99.0, "eta": None, "speed": None}
            )

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
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "overwrites": options.duplicate_policy == "overwrite",
            "writethumbnail": options.embed_thumbnail,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "socket_timeout": 30,
        }
        ydl_options.update(self._component_options())
        audio_postprocessor_args = FormatManager.audio_postprocessor_args(options)
        if audio_postprocessor_args:
            ydl_options["postprocessor_args"] = audio_postprocessor_args
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
                reporter.emit(
                    {"status": DownloadStatus.FINALIZING.value, "progress": 99.0}, force=True
                )
                return existing

        try:
            reporter.emit(
                {"status": DownloadStatus.PREPARING.value, "progress": 0.0}, force=True
            )
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
        deno = next(
            (candidate for candidate in (
                resource_path("deno", "deno.exe"),
                resource_path("deno", "deno"),
            ) if candidate.exists()),
            None,
        )
        if deno is not None:
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

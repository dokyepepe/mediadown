"""Discover and download public PDF/image assets exposed by web pages."""

from __future__ import annotations

import mimetypes
import re
import threading
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from mediadownloader.utils.filenames import sanitize_filename, unique_path
from mediadownloader.utils.validators import is_valid_url
from mediadownloader.version import APP_VERSION


class SiteFileError(RuntimeError):
    """A readable failure while scanning or downloading site assets."""


class SiteFileKind(StrEnum):
    PDF = "pdf"
    IMAGE = "image"

    @property
    def label(self) -> str:
        return "PDF" if self is self.PDF else "Imagem"


@dataclass(frozen=True, slots=True)
class SiteFile:
    url: str
    name: str
    kind: SiteFileKind
    mime_type: str = ""
    referer: str = ""


@dataclass(frozen=True, slots=True)
class SiteScanResult:
    source_url: str
    final_url: str
    page_title: str
    files: tuple[SiteFile, ...]


ProgressCallback = Callable[[int, int | None], None]
OpenUrl = Callable[[Request, float], Any]

IMAGE_EXTENSIONS = {
    ".avif", ".bmp", ".gif", ".heic", ".heif", ".ico", ".jpeg", ".jpg",
    ".png", ".svg", ".tif", ".tiff", ".webp",
}
IMAGE_MIME_EXTENSIONS = {
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
}


def _normalized_web_url(base_url: str, raw: str) -> str | None:
    value = raw.strip().replace("\\/", "/")
    if not value or value.startswith(("data:", "blob:", "javascript:", "mailto:", "#")):
        return None
    try:
        parsed = urlparse(urljoin(base_url, value))
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return urlunparse(parsed._replace(fragment=""))


def _kind_from_url(url: str) -> SiteFileKind | None:
    parsed = urlparse(url)
    decoded = unquote(f"{parsed.path}?{parsed.query}").lower()
    suffix = Path(unquote(parsed.path)).suffix.lower()
    if ".pdf" in decoded:
        return SiteFileKind.PDF
    if suffix == ".pdf":
        return SiteFileKind.PDF
    if suffix in IMAGE_EXTENSIONS or any(extension in decoded for extension in IMAGE_EXTENSIONS):
        return SiteFileKind.IMAGE
    return None


def _name_from_url(url: str, kind: SiteFileKind, suggested: str = "") -> str:
    candidate = unquote(suggested.strip()) or Path(unquote(urlparse(url).path)).name
    fallback = "documento.pdf" if kind is SiteFileKind.PDF else "imagem"
    candidate = sanitize_filename(candidate or fallback)
    suffix = Path(candidate).suffix.lower()
    if kind is SiteFileKind.PDF and suffix != ".pdf":
        candidate = f"{candidate}.pdf"
    return candidate


class _AssetHtmlParser(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = page_url
        self.title_parts: list[str] = []
        self.in_title = False
        self.pending_anchor: tuple[str, str, list[str]] | None = None
        self.candidates: list[tuple[str, SiteFileKind, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): (value or "") for name, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
            return
        if tag == "base" and values.get("href"):
            resolved = _normalized_web_url(self.base_url, values["href"])
            if resolved:
                self.base_url = resolved
            return

        if tag in {"img", "source"}:
            for raw in self._image_sources(values):
                self._add(raw, SiteFileKind.IMAGE, values.get("alt") or values.get("title") or "")

        if tag == "meta" and values.get("property", values.get("name", "")).lower() in {
            "og:image", "og:image:url", "twitter:image", "twitter:image:src",
        }:
            self._add(values.get("content", ""), SiteFileKind.IMAGE, "")

        if tag == "link" and any(
            marker in values.get("rel", "").lower().split()
            for marker in ("icon", "image_src")
        ):
            self._add(values.get("href", ""), SiteFileKind.IMAGE, values.get("title", ""))

        if tag == "a":
            raw = values.get("href", "")
            explicit = (values.get("type", "") + " " + values.get("download", "")).lower()
            kind = _kind_from_url(urljoin(self.base_url, raw)) if raw else None
            if "pdf" in explicit:
                kind = SiteFileKind.PDF
            if kind:
                self._add(raw, kind, values.get("download") or values.get("title") or "")
            elif raw:
                self.pending_anchor = (raw, values.get("title") or "", [])

        if tag in {"embed", "iframe", "object"}:
            raw = values.get("src") or values.get("data") or ""
            explicit_type = values.get("type", "").lower()
            kind = SiteFileKind.PDF if "pdf" in explicit_type else _kind_from_url(
                urljoin(self.base_url, raw),
            )
            if kind:
                self._add(raw, kind, values.get("title", ""))

        style = values.get("style", "")
        for raw in re.findall(r"url\(\s*['\"]?([^)'\"]+)", style, flags=re.IGNORECASE):
            self._add(raw, SiteFileKind.IMAGE, "")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False
        if tag.lower() == "a" and self.pending_anchor is not None:
            raw, suggested, text_parts = self.pending_anchor
            visible_text = " ".join(text_parts).strip()
            if "pdf" in visible_text.casefold() or "pdf" in suggested.casefold():
                self._add(raw, SiteFileKind.PDF, suggested or visible_text)
            self.pending_anchor = None

    def handle_data(self, data: str) -> None:
        if self.in_title and data.strip():
            self.title_parts.append(data.strip())
        if self.pending_anchor is not None and data.strip():
            self.pending_anchor[2].append(data.strip())

    def _image_sources(self, values: dict[str, str]) -> Iterable[str]:
        for key in ("src", "data-src", "data-lazy-src", "poster"):
            if values.get(key):
                yield values[key]
        for key in ("srcset", "data-srcset"):
            for candidate in values.get(key, "").split(","):
                raw = candidate.strip().split()[0] if candidate.strip() else ""
                if raw:
                    yield raw

    def _add(self, raw: str, kind: SiteFileKind, suggested: str) -> None:
        resolved = _normalized_web_url(self.base_url, raw)
        if resolved:
            self.candidates.append((resolved, kind, suggested, ""))


class SiteFileExtractor:
    """Small HTTP/HTML extractor kept independent from the yt-dlp media engine."""

    MAX_PAGE_BYTES = 5 * 1024 * 1024
    MAX_FILE_BYTES = 512 * 1024 * 1024
    USER_AGENT = f"MediaDownloader/{APP_VERSION} (+site-file-extractor)"

    def __init__(self, timeout: float = 25.0, open_url: OpenUrl | None = None) -> None:
        self.timeout = timeout
        self._open_url = open_url or (lambda request, timeout: urlopen(request, timeout=timeout))

    def discover(
        self,
        url: str,
        *,
        include_pdfs: bool = True,
        include_images: bool = True,
    ) -> SiteScanResult:
        source_url = url.strip()
        if not is_valid_url(source_url):
            raise SiteFileError("Informe uma URL HTTP ou HTTPS válida.")
        parsed_source = urlparse(source_url)
        if parsed_source.username is not None or parsed_source.password is not None:
            raise SiteFileError("URLs com usuário ou senha incorporados não são permitidas.")
        if not include_pdfs and not include_images:
            raise SiteFileError("Selecione PDFs, imagens ou ambos antes de analisar.")

        request = self._request(source_url, accept="text/html,application/pdf,image/*;q=0.9,*/*;q=0.2")
        try:
            with self._open_url(request, self.timeout) as response:
                final_url = str(getattr(response, "geturl", lambda: source_url)())
                content_type = self._content_type(response)
                content_length = self._content_length(response)
                if content_length and content_length > self.MAX_PAGE_BYTES and content_type.startswith("text/html"):
                    raise SiteFileError("A página é grande demais para ser analisada com segurança.")

                direct_kind = self._kind_from_response(final_url, content_type)
                if direct_kind is not None:
                    allowed = (direct_kind is SiteFileKind.PDF and include_pdfs) or (
                        direct_kind is SiteFileKind.IMAGE and include_images
                    )
                    files = (
                        SiteFile(
                            final_url,
                            _name_from_url(final_url, direct_kind),
                            direct_kind,
                            content_type,
                            source_url,
                        ),
                    ) if allowed else ()
                    return SiteScanResult(source_url, final_url, _host_title(final_url), files)

                raw = response.read(self.MAX_PAGE_BYTES + 1)
                if len(raw) > self.MAX_PAGE_BYTES:
                    raise SiteFileError("A página é grande demais para ser analisada com segurança.")
                if content_type and "html" not in content_type and not content_type.startswith("text/"):
                    raise SiteFileError("A URL não aponta para uma página, imagem ou PDF compatível.")
                charset = self._charset(response)
                html = raw.decode(charset, errors="replace")
        except SiteFileError:
            raise
        except Exception as error:
            raise SiteFileError(f"Não foi possível acessar o site: {error}") from error

        return self.parse_html(
            source_url=source_url,
            final_url=final_url,
            html=html,
            include_pdfs=include_pdfs,
            include_images=include_images,
        )

    def parse_html(
        self,
        *,
        source_url: str,
        final_url: str,
        html: str,
        include_pdfs: bool = True,
        include_images: bool = True,
    ) -> SiteScanResult:
        parser = _AssetHtmlParser(final_url)
        parser.feed(html)
        parser.close()

        # Some portals expose document URLs inside JSON/script data instead of links.
        embedded_text = re.sub(r"<[^>]+>", " ", html)
        for raw in re.findall(
            r"(?i)(?<=[\"'])(?:https?:)?(?:\\?/\\?/|\\?/|\.\.?/)[^\s'\"<>]+?\.pdf(?:\?[^\s'\"<>]*)?",
            embedded_text,
        ):
            resolved = _normalized_web_url(parser.base_url, raw)
            if resolved:
                parser.candidates.append((resolved, SiteFileKind.PDF, "", "application/pdf"))

        seen: set[str] = set()
        files: list[SiteFile] = []
        for url, kind, suggested, mime_type in parser.candidates:
            if kind is SiteFileKind.PDF and not include_pdfs:
                continue
            if kind is SiteFileKind.IMAGE and not include_images:
                continue
            key = url
            if key in seen:
                continue
            seen.add(key)
            files.append(
                SiteFile(url, _name_from_url(url, kind, suggested), kind, mime_type, final_url)
            )
        files.sort(key=lambda item: (item.kind.value, item.name.casefold(), item.url))
        title = " ".join(parser.title_parts).strip() or _host_title(final_url)
        return SiteScanResult(source_url, final_url, title, tuple(files))

    def download(
        self,
        asset: SiteFile,
        output_dir: str | Path,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        if not is_valid_url(asset.url):
            raise SiteFileError("O endereço do arquivo não é válido.")
        directory = Path(output_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        request = self._request(
            asset.url,
            accept="application/pdf,image/*,*/*;q=0.2",
            referer=asset.referer,
        )
        try:
            with self._open_url(request, self.timeout) as response:
                final_url = str(getattr(response, "geturl", lambda: asset.url)())
                content_type = self._content_type(response)
                if "html" in content_type:
                    raise SiteFileError("O servidor devolveu uma página em vez do arquivo solicitado.")
                detected = self._kind_from_response(final_url, content_type)
                if detected is not None and detected is not asset.kind:
                    raise SiteFileError("O tipo do arquivo recebido não corresponde ao resultado selecionado.")
                total = self._content_length(response)
                if total and total > self.MAX_FILE_BYTES:
                    raise SiteFileError("O arquivo excede o limite de 512 MB.")
                suggested = self._content_disposition_name(response) or asset.name
                name = self._filename_with_extension(suggested, final_url, content_type, asset.kind)
                destination = unique_path(directory / name)
                partial = destination.with_name(f".{destination.name}.part")
                downloaded = 0
                try:
                    with partial.open("wb") as output:
                        while True:
                            if cancel_event is not None and cancel_event.is_set():
                                raise SiteFileError("Download cancelado.")
                            chunk = response.read(64 * 1024)
                            if not chunk:
                                break
                            downloaded += len(chunk)
                            if downloaded > self.MAX_FILE_BYTES:
                                raise SiteFileError("O arquivo excede o limite de 512 MB.")
                            output.write(chunk)
                            if progress:
                                progress(downloaded, total)
                    partial.replace(destination)
                    return destination
                except Exception:
                    partial.unlink(missing_ok=True)
                    raise
        except SiteFileError:
            raise
        except Exception as error:
            raise SiteFileError(f"Não foi possível baixar {asset.name}: {error}") from error

    def _request(self, url: str, *, accept: str, referer: str = "") -> Request:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": accept,
            "Accept-Encoding": "identity",
        }
        if referer:
            headers["Referer"] = referer
        return Request(
            url,
            headers=headers,
            method="GET",
        )

    @staticmethod
    def _content_type(response: Any) -> str:
        headers = getattr(response, "headers", {})
        if hasattr(headers, "get_content_type"):
            return str(headers.get_content_type() or "").lower()
        return str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()

    @staticmethod
    def _charset(response: Any) -> str:
        headers = getattr(response, "headers", {})
        if hasattr(headers, "get_content_charset"):
            return str(headers.get_content_charset() or "utf-8")
        match = re.search(r"charset=([^;\s]+)", str(headers.get("Content-Type", "")), re.I)
        return match.group(1).strip("'\"") if match else "utf-8"

    @staticmethod
    def _content_length(response: Any) -> int | None:
        raw = str(getattr(response, "headers", {}).get("Content-Length", "") or "")
        try:
            value = int(raw)
            return value if value >= 0 else None
        except ValueError:
            return None

    @staticmethod
    def _content_disposition_name(response: Any) -> str:
        raw = str(getattr(response, "headers", {}).get("Content-Disposition", "") or "")
        extended = re.search(r"filename\*\s*=\s*(?:UTF-8'')?([^;]+)", raw, re.I)
        regular = re.search(r"filename\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^;]+))", raw, re.I)
        value = extended.group(1) if extended else next(
            (part for part in (regular.groups() if regular else ()) if part),
            "",
        )
        return unquote(value.strip().strip("'\""))

    @staticmethod
    def _kind_from_response(url: str, content_type: str) -> SiteFileKind | None:
        if content_type == "application/pdf":
            return SiteFileKind.PDF
        if content_type.startswith("image/"):
            return SiteFileKind.IMAGE
        return _kind_from_url(url)

    @staticmethod
    def _filename_with_extension(
        suggested: str,
        final_url: str,
        content_type: str,
        kind: SiteFileKind,
    ) -> str:
        name = sanitize_filename(suggested or _name_from_url(final_url, kind))
        suffix = Path(name).suffix.lower()
        if kind is SiteFileKind.PDF:
            return name if suffix == ".pdf" else f"{name}.pdf"
        if suffix in IMAGE_EXTENSIONS:
            return name
        extension = IMAGE_MIME_EXTENSIONS.get(content_type) or mimetypes.guess_extension(content_type)
        return f"{name}{extension or '.img'}"


def _host_title(url: str) -> str:
    return (urlparse(url).hostname or "Site").removeprefix("www.")

from __future__ import annotations

from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from mediadownloader.core.site_files import (
    SiteFile,
    SiteFileError,
    SiteFileExtractor,
    SiteFileKind,
)


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str,
        content_type: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = BytesIO(body)
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body))
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args) -> None:
        self._body.close()


def test_parser_discovers_relative_pdfs_embeds_and_responsive_images() -> None:
    html = """
        <html><head><title>Portal de documentos</title>
        <meta property="og:image" content="/social/card.webp"></head>
        <body>
          <a href="docs/relatorio.pdf#page=2">Relatório</a>
          <iframe src="/viewer/manual.pdf"></iframe>
          <img src="/img/capa.jpg" srcset="/img/capa-small.png 1x, /img/capa@2x.png 2x">
          <img data-src="https://cdn.example.net/foto.avif">
        </body></html>
    """

    result = SiteFileExtractor().parse_html(
        source_url="https://example.com/portal",
        final_url="https://example.com/area/index.html",
        html=html,
    )

    assert result.page_title == "Portal de documentos"
    assert {item.url for item in result.files if item.kind is SiteFileKind.PDF} == {
        "https://example.com/area/docs/relatorio.pdf",
        "https://example.com/viewer/manual.pdf",
    }
    assert {item.url for item in result.files if item.kind is SiteFileKind.IMAGE} == {
        "https://example.com/social/card.webp",
        "https://example.com/img/capa.jpg",
        "https://example.com/img/capa-small.png",
        "https://example.com/img/capa@2x.png",
        "https://cdn.example.net/foto.avif",
    }


def test_parser_finds_pdf_urls_inside_script_and_deduplicates() -> None:
    html = r"""
        <a href="/files/edital.pdf">PDF</a>
        <script>window.documentUrl = "\/files\/edital.pdf?download=1";</script>
        <script>window.copy = "\/files\/edital.pdf?download=1";</script>
    """

    result = SiteFileExtractor().parse_html(
        source_url="https://example.com",
        final_url="https://example.com/noticias/",
        html=html,
        include_images=False,
    )

    assert [item.url for item in result.files] == [
        "https://example.com/files/edital.pdf",
        "https://example.com/files/edital.pdf?download=1",
    ]


def test_parser_recognizes_pdf_label_and_query_downloads() -> None:
    html = """
        <a href="/download?id=42"><strong>Baixar PDF</strong></a>
        <a href="/download?file=guia.pdf&token=publico">Guia</a>
    """

    result = SiteFileExtractor().parse_html(
        source_url="https://example.com",
        final_url="https://example.com/portal/",
        html=html,
        include_images=False,
    )

    assert {item.url for item in result.files} == {
        "https://example.com/download?id=42",
        "https://example.com/download?file=guia.pdf&token=publico",
    }


def test_discover_accepts_direct_pdf_response() -> None:
    def open_url(_request, _timeout):
        return FakeResponse(
            b"%PDF-1.7\n",
            url="https://cdn.example.com/report?id=1",
            content_type="application/pdf",
        )

    result = SiteFileExtractor(open_url=open_url).discover(
        "https://example.com/download/report?id=1",
        include_images=False,
    )

    assert len(result.files) == 1
    assert result.files[0].kind is SiteFileKind.PDF
    assert result.files[0].name.endswith(".pdf")


def test_download_uses_server_filename_and_atomic_destination(tmp_path: Path) -> None:
    payload = b"%PDF-1.7\ncontent"
    seen_referer: list[str | None] = []

    def open_url(request, _timeout):
        seen_referer.append(request.get_header("Referer"))
        return FakeResponse(
            payload,
            url="https://cdn.example.com/file?id=42",
            content_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename*=UTF-8''Relat%C3%B3rio%202026.pdf"},
        )

    progress: list[tuple[int, int | None]] = []
    asset = SiteFile(
        "https://cdn.example.com/file?id=42",
        "documento.pdf",
        SiteFileKind.PDF,
        referer="https://example.com/portal",
    )
    destination = SiteFileExtractor(open_url=open_url).download(
        asset,
        tmp_path,
        progress=lambda current, total: progress.append((current, total)),
    )

    assert destination.name == "Relatório 2026.pdf"
    assert destination.read_bytes() == payload
    assert progress[-1] == (len(payload), len(payload))
    assert seen_referer == ["https://example.com/portal"]
    assert not list(tmp_path.glob("*.part"))


def test_download_rejects_html_error_page(tmp_path: Path) -> None:
    def open_url(_request, _timeout):
        return FakeResponse(
            b"<html>login</html>",
            url="https://example.com/login",
            content_type="text/html",
        )

    asset = SiteFile("https://example.com/private.pdf", "private.pdf", SiteFileKind.PDF)
    with pytest.raises(SiteFileError, match="página"):
        SiteFileExtractor(open_url=open_url).download(asset, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_scan_requires_at_least_one_file_kind() -> None:
    with pytest.raises(SiteFileError, match="Selecione"):
        SiteFileExtractor().discover(
            "https://example.com",
            include_pdfs=False,
            include_images=False,
        )

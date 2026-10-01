"""Batch enqueue and per-download trim/fade wiring."""

import threading
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from mediadownloader.models import DownloadOptions, MediaType
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.ui.main_window import MainWindow
from mediadownloader.ui.pages.home_page import HomePage


class FakeExtractor:
    pass


class QueueRecorder:
    def __init__(self) -> None:
        self.items: list[tuple] = []

    def add(self, item, options) -> None:
        self.items.append((item, options))


class WindowDouble:
    def __init__(self) -> None:
        self.queue = QueueRecorder()
        self.navigation: list[int] = []

    def _navigate(self, index: int) -> None:
        self.navigation.append(index)


def _page(qtbot, tmp_path: Path) -> HomePage:
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    page = HomePage(FakeExtractor(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(page)
    return page


def test_batch_button_appears_only_with_more_than_one_address(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)

    assert page.batch_button.isHidden()

    page.url_input.setPlainText("https://a.example/1")
    assert page.batch_button.isHidden()

    page.url_input.setPlainText("https://a.example/1\nhttps://a.example/2\nhttps://a.example/3")
    assert not page.batch_button.isHidden()
    assert page.batch_button.text() == "LOTE 3"


def test_queue_batch_emits_every_address_with_shared_options(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    captured: list[tuple] = []
    page.batch_requested.connect(lambda urls, options: captured.append((urls, options)))
    page.destination.setText(str(tmp_path / "destino"))
    page.url_input.setPlainText(
        "https://www.youtube.com/watch?v=abc\nhttps://vimeo.com/9"
    )

    page.queue_batch()

    assert len(captured) == 1
    urls, options = captured[0]
    assert urls == ["https://www.youtube.com/watch?v=abc", "https://vimeo.com/9"]
    assert options.output_dir == str(tmp_path / "destino")
    assert (tmp_path / "destino").is_dir()


def test_queue_batch_needs_two_addresses(qtbot, tmp_path, monkeypatch) -> None:
    page = _page(qtbot, tmp_path)
    captured: list[tuple] = []
    page.batch_requested.connect(lambda urls, options: captured.append((urls, options)))
    page.url_input.setPlainText("https://a.example/1")

    page.queue_batch()

    assert captured == []
    assert "dois ou mais" in page.notice.text()


def test_queue_batch_reports_unusable_destination(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    captured: list[tuple] = []
    page.batch_requested.connect(lambda urls, options: captured.append((urls, options)))
    blocker = tmp_path / "arquivo"
    blocker.write_text("x", encoding="utf-8")
    page.destination.setText(str(blocker / "filha"))
    page.url_input.setPlainText("https://a.example/1\nhttps://a.example/2")

    page.queue_batch()

    assert captured == []
    assert "destino" in page.notice.text()


def test_queue_batch_fills_queue_with_provisional_titles(tmp_path) -> None:
    window = WindowDouble()
    options = DownloadOptions(output_dir=str(tmp_path))

    MainWindow._queue_batch(  # type: ignore[arg-type]
        window,
        ["https://www.youtube.com/watch?v=abc", "https://vimeo.com/9"],
        options,
    )

    items = [item for item, _ in window.queue.items]
    assert [item.title for item in items] == ["Link 1", "Link 2"]
    assert [item.author for item in items] == ["youtube.com", "vimeo.com"]
    assert all(item.provisional_title for item in items)
    assert all(item.output_path == str(tmp_path) for item in items)
    assert window.navigation == []


def test_batch_gives_each_item_its_own_options_copy(tmp_path) -> None:
    window = WindowDouble()
    options = DownloadOptions(output_dir=str(tmp_path), fade_in_seconds=2.0)

    MainWindow._queue_batch(window, ["https://a.example/1", "https://a.example/2"], options)  # type: ignore[arg-type]

    first, second = (opts for _, opts in window.queue.items)
    assert first is not second
    assert first.fade_in_seconds == second.fade_in_seconds == 2.0


def test_queue_batch_reports_empty_field(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    captured: list[tuple] = []
    page.batch_requested.connect(lambda urls, options: captured.append((urls, options)))

    page.queue_batch()

    assert captured == []


def test_paste_url_fills_many_addresses(qtbot, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    page = _page(qtbot, tmp_path)
    monkeypatch.setattr(
        QApplication.clipboard(),
        "text",
        lambda: "https://a.example/1 https://b.example/2",
    )

    page.paste_url()

    assert page.url_input.toPlainText() == "https://a.example/1\nhttps://b.example/2"
    assert not page.batch_button.isHidden()


def test_paste_url_rejects_text_without_links(qtbot, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    page = _page(qtbot, tmp_path)
    monkeypatch.setattr(QApplication.clipboard(), "text", lambda: "só texto")

    page.paste_url()

    assert page.url_input.toPlainText() == ""
    assert "não contém uma URL válida" in page.notice.text()


def test_analyze_uses_the_first_address(qtbot, tmp_path, monkeypatch) -> None:
    page = _page(qtbot, tmp_path)
    started: list[str] = []
    monkeypatch.setattr(page, "_cookie_source_for", lambda url: ("", ""))
    monkeypatch.setattr(
        page.pool,
        "start",
        lambda worker: started.append(worker.url),
    )
    page.url_input.setPlainText("https://a.example/1\nhttps://a.example/2")

    page.analyze()

    assert started == ["https://a.example/1"]
    assert not page.analyze_button.isEnabled()
    assert "Analisando" in page.notice.text()


def test_analyze_reports_invalid_field(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    page.url_input.setPlainText("   ")

    page.analyze()

    assert "Insira uma URL" in page.notice.text()
    assert page.analyze_button.isEnabled()


def test_analyze_reports_unsupported_address(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    page.url_input.setPlainText("https://localhost/1")

    page.analyze()

    assert page.analyze_button.isEnabled()
    assert page.notice.text()


def test_download_options_carry_editing_choices(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    page.url_input.setPlainText("https://a.example/1\nhttps://a.example/2")
    page.trim_start.setValue(12.0)
    page.trim_duration.setValue(90.0)
    page.fade_in.setValue(1.5)
    page.fade_out.setValue(2.0)
    page.editor_compatible.setChecked(True)
    page.multilingual_subtitles.setChecked(True)
    captured: list[tuple] = []
    page.batch_requested.connect(lambda urls, options: captured.append((urls, options)))

    page.queue_batch()

    options = captured[0][1]
    assert options.trim_start_seconds == 12.0
    assert options.trim_duration_seconds == 90.0
    assert options.fade_in_seconds == 1.5
    assert options.fade_out_seconds == 2.0
    assert options.editor_compatible is True
    assert options.all_subtitles is True
    assert options.needs_post_processing is True


def test_download_options_without_editing_skip_post_processing() -> None:
    assert DownloadOptions().needs_post_processing is False


def test_queue_download_keeps_single_media_flow(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)
    captured: list[tuple] = []
    page.download_requested.connect(lambda *args: captured.append(args))

    class Media:
        url = "https://a.example/1"
        webpage_url = "https://a.example/1"
        title = "Um vídeo"
        is_playlist = False
        download_supported = True

    media = Media()
    page.media = media  # type: ignore[assignment]
    page.destination.setText(str(tmp_path))

    page.queue_download()

    assert len(captured) == 1
    assert captured[0][0] is media
    assert captured[0][2] == []


def test_queue_download_reports_spotify_restriction(qtbot, tmp_path) -> None:
    page = _page(qtbot, tmp_path)

    class SpotifyMedia:
        url = "https://open.spotify.com/track/1"
        webpage_url = "https://open.spotify.com/track/1"
        title = "Faixa"
        is_playlist = False
        download_supported = False

    page.media = SpotifyMedia()  # type: ignore[assignment]
    shown: list[bool] = []
    original = QMessageBox.information

    try:
        QMessageBox.information = staticmethod(lambda *args, **kwargs: shown.append(True))  # type: ignore[assignment]
        page.queue_download()
    finally:
        QMessageBox.information = original  # type: ignore[assignment]

    assert shown == []
    assert "Spotify" in page.notice.text()


@pytest.mark.parametrize("suffix", [".mp4", ".mp3"])
def test_post_process_returns_the_edited_file(tmp_path, monkeypatch, suffix) -> None:
    from mediadownloader.core import downloader as downloader_module

    source = tmp_path / f"origem{suffix}"
    source.write_bytes(b"conteudo")
    edited = tmp_path / f"origem.edited{suffix}"
    edited.write_bytes(b"editado")
    calls: dict = {}

    class FFmpegDouble:
        available = True

        def location(self) -> str:
            return ""

        def duration(self, path: Path) -> float:
            return 120.0

        def post_process(self, path: Path, **kwargs) -> Path:
            calls["source"] = path
            calls.update(kwargs)
            return edited

    engine = downloader_module.DownloadEngine.__new__(downloader_module.DownloadEngine)
    engine.ffmpeg = FFmpegDouble()  # type: ignore[assignment]
    item = downloader_module.DownloadItem(
        url="https://a.example/1", title="T", output_path=str(tmp_path)
    )
    options = DownloadOptions(
        media_type=MediaType.VIDEO,
        trim_start_seconds=10.0,
        trim_duration_seconds=30.0,
        fade_in_seconds=1.0,
        fade_out_seconds=2.0,
    )

    result = downloader_module.DownloadEngine._post_process(
        engine,  # type: ignore[arg-type]
        item,
        str(source),
        options,
        _SilentReporter(),
        threading.Event(),
    )

    assert result == str(edited)
    assert calls["source"] == source
    assert calls["start_seconds"] == 10.0
    assert calls["duration_seconds"] == 30.0
    assert calls["has_video"] is True
    assert "afade=t=in" in calls["audio_filter"]
    assert "afade=t=out" in calls["audio_filter"]


class _SilentReporter:
    def emit(self, update, *, force: bool = False) -> bool:
        return True

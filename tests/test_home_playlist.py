from PySide6.QtCore import Qt

from mediadownloader.models import DownloadOptions, MediaInfo, PlaylistEntry
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.ui.main_window import MainWindow
from mediadownloader.ui.pages.home_page import HomePage


class FakeExtractor:
    pass


def _playlist() -> MediaInfo:
    return MediaInfo(
        url="https://example.com/playlist",
        webpage_url="https://example.com/playlist",
        title="Minha playlist",
        is_playlist=True,
        playlist_count=3,
        entries=[
            PlaylistEntry("https://example.com/1", "Primeiro", 1),
            PlaylistEntry("https://example.com/2", "Segundo", 2),
            PlaylistEntry("https://example.com/3", "Terceiro", 3),
        ],
    )


def test_playlist_supports_ignored_selected_individual_and_all(qtbot, tmp_path) -> None:
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("general.download_dir", str(tmp_path))
    page = HomePage(FakeExtractor(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(page)
    captured: list[list] = []
    page.download_requested.connect(lambda _media, _options, entries: captured.append(entries))
    page.url_input.setText("https://example.com/playlist")
    page._analysis_complete(_playlist())

    assert page.playlist_list.count() == 3
    assert "(3)" in page.playlist_title.text()

    page.playlist_list.item(1).setCheckState(Qt.CheckState.Unchecked)
    page.queue_download()
    assert [entry.title for entry in captured[-1]] == ["Primeiro", "Terceiro"]

    page.playlist_list.setCurrentRow(1)
    page._queue_current_playlist_item()
    assert [entry.title for entry in captured[-1]] == ["Segundo"]

    page._queue_all_playlist_items()
    assert [entry.title for entry in captured[-1]] == ["Primeiro", "Segundo", "Terceiro"]
    assert all(
        page.playlist_list.item(index).checkState() == Qt.CheckState.Checked
        for index in range(page.playlist_list.count())
    )

    assert page.url_input.text() == "https://example.com/playlist"
    assert not page.result.isHidden()


def test_adding_download_keeps_home_page_visible(tmp_path) -> None:
    class QueueRecorder:
        def __init__(self) -> None:
            self.items = []

        def add(self, item, options) -> None:
            self.items.append((item, options))

    class WindowDouble:
        def __init__(self) -> None:
            self.queue = QueueRecorder()
            self.navigation: list[int] = []

        def _navigate(self, index: int) -> None:
            self.navigation.append(index)

    window = WindowDouble()
    options = DownloadOptions(output_dir=str(tmp_path))

    MainWindow._queue_media(window, _playlist(), options, [_playlist().entries[0]])  # type: ignore[arg-type]

    assert len(window.queue.items) == 1
    assert window.navigation == []


def test_media_type_switches_to_its_own_destination(qtbot, tmp_path) -> None:
    settings = SettingsService(tmp_path / "settings.json")
    video_dir = tmp_path / "videos"
    audio_dir = tmp_path / "audios"
    settings.set("storage.video_dir", str(video_dir))
    settings.set("storage.audio_dir", str(audio_dir))
    page = HomePage(FakeExtractor(), settings)  # type: ignore[arg-type]
    qtbot.addWidget(page)

    assert page.destination.text() == str(video_dir)
    page.audio_button.click()
    assert page.destination.text() == str(audio_dir)
    page.video_button.click()
    assert page.destination.text() == str(video_dir)

"""Settings sections that came from the mobile edition: gate, stats, backup, sites."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QDialog, QMessageBox

from mediadownloader.core import FFmpegManager
from mediadownloader.core.queue_manager import QueueManager
from mediadownloader.services import backup_service
from mediadownloader.services.history_service import HistoryService
from mediadownloader.services.settings_service import SettingsService
from mediadownloader.services.spotify_service import SpotifyService
from mediadownloader.ui.pages.settings_page import SettingsPage
from mediadownloader.ui.theme import apply_theme


class NeverRunEngine:
    def download(self, *args, **kwargs):
        raise AssertionError("A fila não deve iniciar download nos testes de configuração")


def _page(qapp, qtbot, tmp_path: Path) -> tuple[SettingsPage, SettingsService, QueueManager]:
    apply_theme(qapp, "light")
    ffmpeg = FFmpegManager()
    settings = SettingsService(tmp_path / "settings.json")
    # Point every folder at tmp_path so the storage card never walks the real
    # download directories while the test runs.
    settings.set("general.download_dir", str(tmp_path))
    settings.update_section(
        "storage",
        {
            "video_dir": str(tmp_path),
            "audio_dir": str(tmp_path),
            "site_files_dir": str(tmp_path),
        },
    )
    queue = QueueManager(NeverRunEngine(), HistoryService(tmp_path / "h.sqlite3"), concurrency=2)  # type: ignore[arg-type]
    page = SettingsPage(settings, queue, ffmpeg, SpotifyService(settings))
    qtbot.addWidget(page)
    return page, settings, queue


def _silence_dialogs(monkeypatch) -> list[tuple[str, tuple]]:
    seen: list[tuple[str, tuple]] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *args, **kwargs: seen.append(("info", args[1:])))
    )
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *args, **kwargs: seen.append(("warn", args[1:])))
    )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    )
    return seen


def _completed_item(url: str, directory: Path):
    from mediadownloader.models import DownloadItem, DownloadStatus, MediaType

    return DownloadItem(
        url=url,
        title="Concluído",
        author="Autor",
        output_path=str(directory),
        platform="youtube",
        media_type=MediaType.VIDEO,
        format="mp4",
        quality="720",
        status=DownloadStatus.COMPLETED,
        file_size=2_000_000,
    )


def test_theme_offers_the_mobile_four_options(qapp, qtbot, tmp_path: Path) -> None:
    page, _settings, _queue = _page(qapp, qtbot, tmp_path)

    values = [page.theme.itemData(index) for index in range(page.theme.count())]

    assert values == ["system", "light", "dark", "amoled"]


def test_window_and_free_space_rules_are_persisted_and_applied(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    page, settings, queue = _page(qapp, qtbot, tmp_path)
    _silence_dialogs(monkeypatch)

    page.window_enabled.setChecked(True)
    page.window_start.setTime(QTime(23, 0))
    page.window_end.setTime(QTime(6, 30))
    page.minimum_free_mb.setValue(256)
    page.keep_awake.setChecked(True)

    assert page.window_start.isEnabled() is True

    page.save()

    assert settings.get("downloads.window_start_minute") == 1_380
    assert settings.get("downloads.window_end_minute") == 390
    assert settings.get("downloads.minimum_free_mb") == 256
    assert queue.gate_config.window_start_minute == 1_380
    assert queue.gate_config.minimum_free_bytes == 256 * 1024 * 1024
    assert queue.keep_awake is True


def test_disabling_the_window_locks_its_time_fields(qapp, qtbot, tmp_path: Path) -> None:
    page, _settings, _queue = _page(qapp, qtbot, tmp_path)

    page.window_enabled.setChecked(False)

    assert page.window_start.isEnabled() is False
    assert page.window_end.isEnabled() is False


def test_a_blocked_gate_is_explained_in_the_settings_page(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    page, _settings, queue = _page(qapp, qtbot, tmp_path)

    queue.gate_blocked = True
    queue.gate_reason = "Janela agendada (23:00–06:00)"
    page._refresh_gate_status()

    assert "23:00" in page.gate_status.text()
    assert page.gate_status_panel.property("state") == "warning"


def test_an_invalid_proxy_blocks_saving_and_explains_why(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    page, settings, _queue = _page(qapp, qtbot, tmp_path)
    seen = _silence_dialogs(monkeypatch)

    page.proxy_type.setCurrentIndex(page.proxy_type.findData("http"))
    page.proxy_url.setText("127.0.0.1:8080")
    page.proxy_url.editingFinished.emit()

    assert "esquemas" in page.proxy_status.text()

    page.save()

    assert settings.get("network.proxy_url") == ""
    assert seen[0][0] == "warn"


def test_impersonation_is_offered_globally_and_per_profile(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    from mediadownloader.ui.pages.settings_page import ProfileDialog

    page, settings, _queue = _page(qapp, qtbot, tmp_path)
    _silence_dialogs(monkeypatch)

    dialog = ProfileDialog(page)
    qtbot.addWidget(dialog)
    dialog.label_edit.setText("Conta")
    dialog.hosts_edit.setText("youtube.com")
    dialog.file_edit.setText(str(tmp_path / "cookies.txt"))
    dialog.impersonate.setCurrentIndex(dialog.impersonate.findData("chrome"))
    dialog.accept()

    data = dialog.profile_data()
    assert data["impersonate"] == "chrome"

    page.impersonate.setCurrentIndex(page.impersonate.findData("firefox"))
    page.save()

    assert settings.get("cookies.impersonate") == "firefox"


def test_storage_section_reports_history_and_temporary_usage(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    page, settings, _queue = _page(qapp, qtbot, tmp_path)
    import mediadownloader.ui.pages.settings_page as settings_module

    monkeypatch.setattr(
        settings_module.stats_service, "database_path", lambda: tmp_path / "h.sqlite3"
    )
    HistoryService(tmp_path / "h.sqlite3").upsert(_completed_item("https://example.com/a", tmp_path))
    (tmp_path / "resto.mp4.part").write_bytes(b"z" * 12)

    page._refresh_stats()

    assert page.stats_completed.text() == "1"
    assert page.stats_downloaded.text() != "—"
    assert page.stats_temporary.text() == "12 B (1 arquivos)"
    assert page.stats_free.text() not in ("", "—")


def test_cleanup_only_removes_temporary_files(monkeypatch, qapp, qtbot, tmp_path: Path) -> None:
    page, _settings, _queue = _page(qapp, qtbot, tmp_path)
    _silence_dialogs(monkeypatch)
    media = tmp_path / "musica.mp3"
    media.write_bytes(b"final")
    (tmp_path / "musica.mp3.part").write_bytes(b"parcial")

    page._cleanup_temporaries()

    assert media.exists()
    assert not (tmp_path / "musica.mp3.part").exists()


def test_backup_round_trip_through_the_settings_page(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QFileDialog

    page, settings, queue = _page(qapp, qtbot, tmp_path)
    _silence_dialogs(monkeypatch)
    target = tmp_path / backup_service.BACKUP_FILENAME

    settings.update_section("general", {"theme": "amoled"})
    page._load()
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *args, **kwargs: (str(target), ""))
    )
    page._export_backup()
    assert target.exists()

    settings.update_section("general", {"theme": "light"})
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *args, **kwargs: (str(target), ""))
    )
    page._import_backup()

    assert settings.get("general.theme") == "amoled"
    assert page.theme.currentData() == "amoled"


def test_importing_a_foreign_file_is_refused(
    monkeypatch, qapp, qtbot, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QFileDialog

    page, settings, _queue = _page(qapp, qtbot, tmp_path)
    seen = _silence_dialogs(monkeypatch)
    bogus = tmp_path / "estranho.json"
    bogus.write_text('{"format": 99, "settings": {}}', encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *args, **kwargs: (str(bogus), ""))
    )

    page._import_backup()

    assert settings.get("general.theme") == "system"
    assert seen and seen[-1][0] == "warn"


def test_site_section_lists_every_catalogued_platform(qapp, qtbot, tmp_path: Path) -> None:
    page, _settings, _queue = _page(qapp, qtbot, tmp_path)

    text = page.site_list.text()

    assert "YouTube" in text
    assert "Spotify" in text
    assert "Metadados apenas" in text

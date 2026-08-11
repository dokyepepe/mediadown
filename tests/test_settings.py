from pathlib import Path

from mediadownloader.services.settings_service import SettingsService


def test_settings_persist_and_merge_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = SettingsService(path)
    settings.set("downloads.concurrent", 4)
    loaded = SettingsService(path)
    assert loaded.get("downloads.concurrent") == 4
    assert loaded.get("general.language") == "pt_BR"


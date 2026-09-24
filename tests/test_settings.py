import json
from pathlib import Path

from mediadownloader.services.settings_service import SettingsService


def test_settings_persist_and_merge_defaults(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = SettingsService(path)
    settings.set("downloads.concurrent", 4)
    loaded = SettingsService(path)
    assert loaded.get("downloads.concurrent") == 4
    assert loaded.get("general.language") == "pt_BR"


def test_legacy_download_directory_migrates_to_each_storage_type(tmp_path: Path):
    path = tmp_path / "settings.json"
    legacy = str(tmp_path / "meus-downloads")
    path.write_text(json.dumps({"general": {"download_dir": legacy}}), encoding="utf-8")

    settings = SettingsService(path)

    assert settings.get("storage.video_dir") == legacy
    assert settings.get("storage.audio_dir") == legacy
    assert settings.get("storage.site_files_dir") == legacy


def test_rate_limit_defaults_to_unlimited(tmp_path: Path):
    settings = SettingsService(tmp_path / "settings.json")
    assert settings.get("network.rate_limit_kbps") == 0


def test_rate_limit_persists(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = SettingsService(path)
    settings.update_section("network", {"rate_limit_kbps": 512})
    loaded = SettingsService(path)
    assert loaded.get("network.rate_limit_kbps") == 512


def test_cookie_profiles_default_to_empty(tmp_path: Path):
    settings = SettingsService(tmp_path / "settings.json")
    assert settings.get("cookies.profiles") == []


def test_cookie_profiles_persist(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = SettingsService(path)
    profiles = [{"id": "a", "label": "Conta", "hosts": ["youtube.com"], "file": "C:\\c.txt"}]
    settings.update_section("cookies", {"profiles": profiles})
    loaded = SettingsService(path)
    assert loaded.get("cookies.profiles") == profiles


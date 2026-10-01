from __future__ import annotations

import json
from pathlib import Path

import pytest

from mediadownloader.services import backup_service
from mediadownloader.services.backup_service import BACKUP_FILENAME, BackupError


def _profile(tmp_path: Path, profile_id: str = "abc123") -> dict:
    cookie = tmp_path / f"{profile_id}.txt"
    cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    return {
        "id": profile_id,
        "label": "Conta principal",
        "hosts": ["youtube.com"],
        "file": str(cookie),
        "impersonate": "chrome",
    }


def test_export_inlines_cookie_bodies_and_normalises_profiles(tmp_path: Path):
    settings = {"general": {"theme": "amoled"}, "spotify": {"client_id": "publico"}}
    payload = backup_service.export(settings, [_profile(tmp_path)])

    assert payload["format"] == backup_service.BACKUP_FORMAT
    assert payload["application"] == "MediaDownloader"
    assert json.loads(json.dumps(payload))["cookie_profiles"] == [
        {
            "id": "abc123",
            "label": "Conta principal",
            "hosts": ["youtube.com"],
            "impersonate": "chrome",
        }
    ]
    assert "Netscape" in payload["cookie_files"]["abc123"]
    # The absolute path never travels; only the body does.
    assert str(tmp_path) not in json.dumps(payload, ensure_ascii=False)


def test_export_skips_profiles_without_an_id(tmp_path: Path):
    payload = backup_service.export({}, [{"label": "sem id", "file": str(tmp_path)}])
    assert payload["cookie_profiles"] == []
    assert payload["cookie_files"] == {}


def test_round_trip_restores_cookies_to_the_local_store(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIA_DOWNLOADER_DATA_DIR", str(tmp_path / "dados"))
    profile = _profile(tmp_path)
    raw = backup_service.dumps({"general": {"theme": "dark"}}, [profile])

    payload = backup_service.loads(raw)
    restored = backup_service.apply(payload)

    assert len(restored) == 1
    entry = restored[0]
    assert entry["id"] == "abc123"
    assert entry["impersonate"] == "chrome"
    new_path = Path(entry["file"])
    assert new_path != Path(profile["file"])
    assert "Netscape" in new_path.read_text(encoding="utf-8")


def test_apply_removes_a_stale_local_copy_when_the_backup_has_none(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_DOWNLOADER_DATA_DIR", str(tmp_path / "dados"))
    stale = backup_service.profile_cookie_path("sem-corpo")
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("antigo", encoding="utf-8")

    restored = backup_service.apply(
        backup_service.BackupPayload(
            profiles=[{"id": "sem-corpo", "label": "x", "hosts": []}]
        )
    )

    assert not stale.exists()
    assert restored[0]["label"] == "x"


def test_loads_rejects_malformed_documents():
    with pytest.raises(BackupError):
        backup_service.loads("isto não é json")
    with pytest.raises(BackupError):
        backup_service.loads("[]")
    with pytest.raises(BackupError):
        backup_service.loads(json.dumps({"format": 999, "settings": {}}))
    with pytest.raises(BackupError):
        backup_service.loads(json.dumps({"format": 1, "settings": []}))
    with pytest.raises(BackupError):
        backup_service.loads(
            json.dumps({"format": 1, "settings": {}, "cookie_files": ["texto"]})
        )


def test_dumps_is_indented_utf8_json():
    raw = backup_service.dumps({"filenames": {"template": "%(title)s.%(ext)s"}}, [])
    assert "\n" in raw
    document = json.loads(raw)
    assert document["settings"]["filenames"]["template"] == "%(title)s.%(ext)s"
    assert document["cookie_profiles"] == []


def test_backup_filename_is_stable():
    assert BACKUP_FILENAME == "media_downloader_settings_backup.json"

from mediadownloader.utils.paths import app_data_dir, asset_path, project_root
from PySide6.QtCore import QLockFile


def test_single_instance_lock_is_acquired_before_component_activation():
    main_source = (project_root() / "src" / "mediadownloader" / "main.py").read_text(
        encoding="utf-8"
    )

    assert main_source.index("instance_lock.tryLock(0)") < main_source.index(
        "activation = activate_updated_ytdlp()"
    )


def test_single_instance_lock_releases_cleanly(tmp_path):
    lock_path = str(tmp_path / "MediaDownloader.lock")
    first = QLockFile(lock_path)
    second = QLockFile(lock_path)

    assert first.tryLock(0) is True
    assert second.tryLock(0) is False
    first.unlock()
    assert second.tryLock(0) is True
    second.unlock()


def test_development_paths_point_to_project():
    assert (project_root() / "pyproject.toml").exists()
    assert asset_path("app.svg").exists()


def test_ytdlp_is_externalized_for_runtime_updates():
    hook = project_root() / "hooks" / "hook-yt_dlp.py"
    spec = (project_root() / "MediaDownloader.spec").read_text(encoding="utf-8")

    assert hook.exists()
    assert 'module_collection_mode = "py"' in hook.read_text(encoding="utf-8")
    assert 'hookspath=[str(root / "hooks")]' in spec


def test_data_directory_can_be_isolated_for_smoke_tests(tmp_path, monkeypatch):
    isolated = tmp_path / "isolated-app-data"
    monkeypatch.setenv("MEDIA_DOWNLOADER_DATA_DIR", str(isolated))

    assert app_data_dir() == isolated.resolve()
    assert isolated.is_dir()


def test_packaged_smoke_uses_an_isolated_data_directory():
    build_script = (project_root() / "scripts" / "build.ps1").read_text(encoding="utf-8")

    assert "MEDIA_DOWNLOADER_DATA_DIR" in build_script
    assert "smoke-data-" in build_script


def test_appimage_build_has_desktop_metadata_and_smoke_test():
    root = project_root()
    build_script = (root / "scripts" / "build_appimage.sh").read_text(encoding="utf-8")

    assert (root / "packaging" / "linux" / "AppRun").exists()
    assert (root / "packaging" / "linux" / "io.github.mediadownloader.MediaDownloader.desktop").exists()
    assert "AppDir" in build_script
    assert "--smoke-test" in build_script
    assert "appimagetool" in build_script


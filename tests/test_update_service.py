from __future__ import annotations

import hashlib
import importlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import pytest

from mediadownloader.services.update_service import UpdateService


def _package_files(
    version: str,
    *,
    metadata_lines: tuple[str, ...] = (),
) -> dict[str, str]:
    return {
        "yt_dlp/__init__.py": (
            "from .version import __version__\n"
            "class YoutubeDL:\n"
            "    def __init__(self, options=None): self.options = options or {}\n"
            "    def close(self): pass\n"
        ),
        "yt_dlp/version.py": f"__version__ = {version!r}\n",
        "yt_dlp/utils.py": "class DownloadError(Exception): pass\n",
        "yt_dlp/extractor/__init__.py": "def gen_extractor_classes(): return [object]\n",
        f"yt_dlp-{version}.dist-info/METADATA": (
            "Metadata-Version: 2.1\nName: yt-dlp\n"
            f"Version: {version}\n"
            + "".join(f"{line}\n" for line in metadata_lines)
        ),
    }


def _write_package(root: Path, version: str) -> Path:
    for relative, content in _package_files(version).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def _wheel_bytes(
    version: str,
    *,
    package_version: str | None = None,
    metadata_lines: tuple[str, ...] = (),
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        for relative, content in _package_files(
            package_version or version,
            metadata_lines=metadata_lines,
        ).items():
            package.writestr(relative, content)
    return output.getvalue()


def _mock_pypi(
    monkeypatch: pytest.MonkeyPatch,
    wheel: bytes,
    version: str,
    *,
    digest: str | None = None,
) -> None:
    expected = digest or hashlib.sha256(wheel).hexdigest()
    payload = {
        "info": {"version": version},
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": f"yt_dlp-{version}-py3-none-any.whl",
                "url": f"https://files.pythonhosted.org/packages/yt_dlp-{version}.whl",
                "digests": {"sha256": expected},
            }
        ],
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        return io.BytesIO(payload_bytes if url.endswith("/json") else wheel)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def _service(tmp_path: Path) -> UpdateService:
    return UpdateService(tmp_path / "components", bundled_version="1.0.0")


def test_pypi_and_runtime_date_versions_are_equivalent() -> None:
    assert UpdateService.versions_equal("2026.7.4", "2026.07.04")
    assert not UpdateService.versions_equal("2026.7.4", "2026.07.05")


def test_newer_version_comparison_handles_zero_padded_dates() -> None:
    assert UpdateService.version_is_newer("2026.07.05", "2026.7.4")
    assert not UpdateService.version_is_newer("2026.07.04", "2026.7.4")


def test_valid_update_is_staged_without_changing_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    result = service.update_ytdlp()
    status = service.status()

    assert result.staged is True
    assert result.restart_required is True
    assert status.current_version == "1.0.0"
    assert status.pending_version == "2.0.0"
    assert status.pending_action == "update"
    assert status.previous_version is None
    assert len([path for path in service.versions_dir.iterdir() if not path.name.startswith(".")]) == 1


def test_invalid_sha_does_not_change_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0", digest="0" * 64)

    with pytest.raises(ValueError, match="SHA-256"):
        service.update_ytdlp()

    status = service.status()
    assert status.current_version == "1.0.0"
    assert status.pending_version is None


def test_wheel_with_different_internal_version_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0", package_version="9.9.9")
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    with pytest.raises(ValueError, match="9.9.9"):
        service.update_ytdlp()

    assert service.status().pending_version is None


def test_wheel_requiring_newer_python_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0", metadata_lines=("Requires-Python: >=99",))
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    with pytest.raises(ValueError, match="exige Python"):
        service.update_ytdlp()

    assert service.status().pending_version is None


def test_wheel_with_unavailable_default_dependency_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes(
        "2.0.0",
        metadata_lines=("Requires-Dist: yt-dlp-ejs==999; extra == 'default'",),
    )
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    with pytest.raises(ValueError, match="yt-dlp-ejs==999"):
        service.update_ytdlp()

    assert service.status().pending_version is None


def test_compatible_runtime_requirements_are_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes(
        "2.0.0",
        metadata_lines=(
            "Requires-Python: >=3.10",
            "Requires-Dist: packaging>=24; extra == 'default'",
        ),
    )
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    assert service.update_ytdlp().staged is True


def test_older_stable_release_never_causes_implicit_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = UpdateService(tmp_path / "components", bundled_version="3.0.0")
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    result = service.update_ytdlp()

    assert result == result.__class__("3.0.0", staged=False, restart_required=False)
    assert service.status().pending_version is None
    assert not list(service.versions_dir.iterdir())


def test_explicit_force_can_stage_a_diagnostic_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = UpdateService(tmp_path / "components", bundled_version="3.0.0")
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")

    assert service.update_ytdlp(force=True).staged is True
    assert service.status().pending_version == "2.0.0"


def test_successful_activation_promotes_candidate_and_keeps_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()
    monkeypatch.setattr(service, "_probe_reference", lambda reference: reference.version)

    activation = service.activate()
    status = service.status()

    assert activation.changed is True
    assert activation.action == "update"
    assert status.current_version == "2.0.0"
    assert status.previous_version == "1.0.0"
    assert status.pending_version is None
    assert status.rollback_available is True


def test_failed_candidate_rolls_back_and_blocks_that_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()

    def probe(reference):
        if reference.version == "2.0.0":
            raise RuntimeError("API incompatível")
        return reference.version

    monkeypatch.setattr(service, "_probe_reference", probe)
    activation = service.activate()
    status = service.status()

    assert activation.automatic_rollback is True
    assert activation.active_version == "1.0.0"
    assert "restaurada automaticamente" in activation.message
    assert status.current_version == "1.0.0"
    assert status.pending_version is None
    assert status.rejected_version == "2.0.0"
    with pytest.raises(RuntimeError, match="bloqueada"):
        service.update_ytdlp()


def test_interrupted_activation_is_rolled_back_without_retrying_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()
    state = json.loads(service.state_path.read_text(encoding="utf-8"))
    state["activation_in_progress"] = True
    service._write_state(state)
    probed: list[str] = []

    def probe(reference):
        probed.append(reference.version)
        return reference.version

    monkeypatch.setattr(service, "_probe_reference", probe)
    activation = service.activate()

    assert activation.automatic_rollback is True
    assert probed == ["1.0.0"]
    assert service.status().rejected_version == "2.0.0"


def test_manual_rollback_can_be_undone_on_next_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    monkeypatch.setattr(service, "_probe_reference", lambda reference: reference.version)
    service.update_ytdlp()
    service.activate()

    rollback = service.request_rollback()
    assert rollback.version == "1.0.0"
    assert service.status().pending_action == "rollback"

    activation = service.activate()
    status = service.status()
    assert activation.action == "rollback"
    assert status.current_version == "1.0.0"
    assert status.previous_version == "2.0.0"


def test_pending_update_can_be_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()

    assert service.cancel_pending_change() is True
    assert service.status().pending_version is None
    assert not [path for path in service.versions_dir.iterdir() if not path.name.startswith(".")]


def test_zip_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.whl"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../outside.py", "bad = True")
    destination = tmp_path / "extract"
    destination.mkdir()

    with pytest.raises(ValueError, match="insegura"):
        UpdateService._safe_extract(archive, destination)

    assert not (tmp_path / "outside.py").exists()


def test_probe_checks_real_version_api_and_origin(tmp_path: Path) -> None:
    bundled = _write_package(tmp_path / "bundled", "1.0.0")
    service = UpdateService(
        tmp_path / "components",
        bundled_version="1.0.0",
        bundled_path=bundled,
    )
    original_path = list(sys.path)
    try:
        activation = service.activate()
        assert activation.active_version == "1.0.0"
        assert Path(sys.path[0]).resolve() == bundled.resolve()
        package = importlib.import_module("yt_dlp")
        assert Path(package.__file__).resolve().is_relative_to(bundled.resolve())
    finally:
        service._clear_ytdlp_modules()
        sys.path[:] = original_path


def test_system_exit_in_candidate_is_contained_and_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundled = _write_package(tmp_path / "bundled", "1.0.0")
    service = UpdateService(
        tmp_path / "components",
        bundled_version="1.0.0",
        bundled_path=bundled,
    )
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()
    candidate = next(path for path in service.versions_dir.iterdir() if path.is_dir())
    (candidate / "yt_dlp" / "__init__.py").write_text(
        "raise SystemExit(9)\n", encoding="utf-8"
    )

    activation = service.activate()

    assert activation.automatic_rollback is True
    assert activation.active_version == "1.0.0"
    assert service.status().rejected_version == "2.0.0"


def test_hanging_candidate_times_out_without_hanging_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mediadownloader.services.update_service as update_module

    bundled = _write_package(tmp_path / "bundled", "1.0.0")
    service = UpdateService(
        tmp_path / "components",
        bundled_version="1.0.0",
        bundled_path=bundled,
    )
    wheel = _wheel_bytes("2.0.0")
    _mock_pypi(monkeypatch, wheel, "2.0.0")
    service.update_ytdlp()
    candidate = next(path for path in service.versions_dir.iterdir() if path.is_dir())
    (candidate / "yt_dlp" / "__init__.py").write_text(
        "import time\ntime.sleep(30)\n", encoding="utf-8"
    )
    monkeypatch.setattr(update_module, "_PROBE_TIMEOUT_SECONDS", 1)

    activation = service.activate()

    assert activation.automatic_rollback is True
    assert "excedeu 1 segundos" in activation.message


def test_stale_bundled_references_follow_the_new_app_bundle(tmp_path: Path) -> None:
    bundled = _write_package(tmp_path / "bundled", "3.0.0")
    service = UpdateService(
        tmp_path / "components",
        bundled_version="3.0.0",
        bundled_path=bundled,
    )
    local = _write_package(service.versions_dir / "2.0.0-local", "2.0.0")
    service.state_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "active": {"source": "local", "version": "2.0.0", "path": local.name},
                "previous": {"source": "bundled", "version": "1.0.0", "path": None},
                "pending": None,
                "pending_action": None,
                "activation_in_progress": False,
                "rejected_version": None,
                "last_event": None,
            }
        ),
        encoding="utf-8",
    )

    assert service.status().previous_version == "3.0.0"
    assert service.request_rollback().version == "3.0.0"
    assert service.activate().active_version == "3.0.0"


def test_stale_active_bundle_is_normalized_without_false_rollback(tmp_path: Path) -> None:
    service = UpdateService(tmp_path / "components", bundled_version="3.0.0")
    service.state_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "active": {"source": "bundled", "version": "1.0.0", "path": None},
                "previous": {"source": "bundled", "version": "1.0.0", "path": None},
                "pending": None,
                "pending_action": None,
                "activation_in_progress": False,
                "rejected_version": None,
                "last_event": None,
            }
        ),
        encoding="utf-8",
    )

    status = service.status()

    assert status.current_version == "3.0.0"
    assert status.previous_version is None
    assert status.rollback_available is False

"""Transactional yt-dlp updates with validation and one-version rollback."""

from __future__ import annotations

import ast
import email.parser
import hashlib
import importlib
import importlib.metadata
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import tokenize
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from mediadownloader.utils.paths import components_dir

LOGGER = logging.getLogger(__name__)
PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
STATE_SCHEMA = 1
MAX_WHEEL_BYTES = 100 * 1024 * 1024
MAX_UNPACKED_BYTES = 300 * 1024 * 1024
_UPDATE_LOCK = threading.RLock()
_ALLOWED_FILE_HOSTS = {"files.pythonhosted.org"}
_PROBE_ARGUMENT = "--internal-ytdlp-probe"
_PROBE_TIMEOUT_SECONDS = 20

try:
    # Capture this before a user-local dist-info directory can ever enter sys.path.
    # Looking it up later could mistake the active update for the bundled fallback.
    _BUNDLED_YTDLP_VERSION = importlib.metadata.version("yt-dlp")
except importlib.metadata.PackageNotFoundError:
    _BUNDLED_YTDLP_VERSION = "não instalado"


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    current_version: str
    previous_version: str | None
    pending_version: str | None
    pending_action: Literal["update", "rollback"] | None
    restart_required: bool
    rollback_available: bool
    rejected_version: str | None
    last_event: str | None
    message: str


@dataclass(frozen=True, slots=True)
class UpdateResult:
    version: str
    staged: bool
    restart_required: bool


@dataclass(frozen=True, slots=True)
class RollbackResult:
    version: str
    restart_required: bool


@dataclass(frozen=True, slots=True)
class ActivationResult:
    active_version: str
    changed: bool = False
    automatic_rollback: bool = False
    action: str | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class _ComponentRef:
    source: Literal["bundled", "local"]
    version: str
    path: str | None = None

    @classmethod
    def from_value(cls, value: object) -> _ComponentRef | None:
        if not isinstance(value, dict):
            return None
        source = value.get("source")
        version = value.get("version")
        path = value.get("path")
        if source not in {"bundled", "local"} or not isinstance(version, str) or not version:
            return None
        if source == "local" and (not isinstance(path, str) or not path):
            return None
        return cls(source=source, version=version, path=path if source == "local" else None)


class UpdateService:
    """Manage immutable component versions and an atomic state pointer."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        bundled_version: str | None = None,
        bundled_path: Path | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else components_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.versions_dir = self.root / "yt-dlp-versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "yt-dlp-state.json"
        self._bundled_version_override = bundled_version
        self._bundled_path = Path(bundled_path).resolve() if bundled_path else None

    def current_ytdlp_version(self) -> str:
        return self.status().current_version

    def latest_ytdlp_version(self, timeout: int = 15) -> str:
        payload = self._pypi_payload(timeout)
        return str(payload["info"]["version"])

    @staticmethod
    def versions_equal(first: str, second: str) -> bool:
        """Compare yt-dlp date versions regardless of PyPI zero normalization."""
        try:
            return Version(first) == Version(second)
        except InvalidVersion:
            return UpdateService._version_key(first) == UpdateService._version_key(second)

    @staticmethod
    def version_is_newer(candidate: str, current: str) -> bool:
        """Return whether a candidate is newer without treating zero-padded dates differently."""
        try:
            return Version(candidate) > Version(current)
        except InvalidVersion:
            return UpdateService._version_key(candidate) > UpdateService._version_key(current)

    def status(self) -> ComponentStatus:
        with _UPDATE_LOCK:
            state = self._load_state()
            active = self._state_ref(state, "active") or self._bundled_ref()
            previous = self._state_ref(state, "previous")
            pending = self._state_ref(state, "pending")
            action = state.get("pending_action")
            if action not in {"update", "rollback"}:
                action = None
            event = state.get("last_event") if isinstance(state.get("last_event"), dict) else {}
            previous_available = previous is not None and self._reference_available(previous)
            return ComponentStatus(
                current_version=active.version,
                previous_version=previous.version if previous_available else None,
                pending_version=pending.version if pending is not None else None,
                pending_action=action,
                restart_required=pending is not None and action is not None,
                rollback_available=previous_available and pending is None,
                rejected_version=(
                    str(state["rejected_version"])
                    if isinstance(state.get("rejected_version"), str)
                    else None
                ),
                last_event=str(event.get("kind")) if event.get("kind") else None,
                message=str(event.get("message") or ""),
            )

    def update_ytdlp(self, timeout: int = 60, *, force: bool = False) -> UpdateResult:
        """Download and validate the newest wheel without changing the loaded version."""
        with _UPDATE_LOCK:
            payload = self._pypi_payload(timeout)
            version = str(payload["info"]["version"])
            state = self._load_state()
            active = self._state_ref(state, "active") or self._bundled_ref()
            pending = self._state_ref(state, "pending")
            if self.versions_equal(version, active.version) and pending is None:
                return UpdateResult(active.version, staged=False, restart_required=False)
            if (
                not force
                and pending is None
                and not self.version_is_newer(version, active.version)
            ):
                # A stable index can temporarily be older than a bundled/nightly build.
                # Never present that as an update or silently downgrade the component.
                return UpdateResult(active.version, staged=False, restart_required=False)
            if (
                pending is not None
                and self.versions_equal(pending.version, version)
                and state.get("pending_action") == "update"
            ):
                return UpdateResult(pending.version, staged=False, restart_required=True)
            if state.get("pending_action") == "rollback":
                raise RuntimeError(
                    "Há uma restauração pronta. Reinicie ou cancele essa alteração antes de atualizar."
                )
            if (
                not force
                and isinstance(state.get("rejected_version"), str)
                and self.versions_equal(str(state["rejected_version"]), version)
            ):
                raise RuntimeError(
                    f"A versão {version} falhou na validação e foi bloqueada. "
                    "Aguarde uma versão mais recente antes de tentar novamente."
                )

            wheel = self._select_wheel(payload)
            wheel_python = wheel.get("requires_python")
            if isinstance(wheel_python, str) and wheel_python.strip():
                self._validate_python_requirement(wheel_python)
            expected_digest = str(wheel.get("digests", {}).get("sha256") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
                raise ValueError("O índice do PyPI não forneceu um SHA-256 válido para o pacote.")

            reference = self._download_and_stage_wheel(
                wheel=wheel,
                expected_version=version,
                expected_digest=expected_digest,
                timeout=timeout,
            )
            state["pending"] = asdict(reference)
            state["pending_action"] = "update"
            state["activation_in_progress"] = False
            state["last_event"] = self._event(
                "update_staged",
                f"Atualização {reference.version} pronta. Reinicie para validar e ativar.",
                version=reference.version,
            )
            self._write_state(state)
            self._garbage_collect(state)
            return UpdateResult(reference.version, staged=True, restart_required=True)

    def request_rollback(self) -> RollbackResult:
        """Schedule the known recovery version for validation at the next startup."""
        with _UPDATE_LOCK:
            state = self._load_state()
            if self._state_ref(state, "pending") is not None:
                raise RuntimeError(
                    "Já existe uma alteração pronta. Cancele-a ou reinicie antes de restaurar."
                )
            previous = self._state_ref(state, "previous")
            if previous is None or not self._reference_available(previous):
                raise RuntimeError("Ainda não há uma versão de recuperação disponível.")
            state["pending"] = asdict(previous)
            state["pending_action"] = "rollback"
            state["activation_in_progress"] = False
            state["last_event"] = self._event(
                "rollback_staged",
                f"Restauração da versão {previous.version} pronta. Reinicie para aplicar.",
                version=previous.version,
            )
            self._write_state(state)
            return RollbackResult(previous.version, restart_required=True)

    def cancel_pending_change(self) -> bool:
        with _UPDATE_LOCK:
            state = self._load_state()
            pending = self._state_ref(state, "pending")
            if pending is None:
                return False
            version = pending.version
            state["pending"] = None
            state["pending_action"] = None
            state["activation_in_progress"] = False
            state["last_event"] = self._event(
                "change_cancelled",
                f"A alteração pendente da versão {version} foi cancelada.",
                version=version,
            )
            self._write_state(state)
            self._garbage_collect(state)
            return True

    def activate(self) -> ActivationResult:
        """Validate the selected version offline and recover automatically on failure."""
        with _UPDATE_LOCK:
            state = self._load_state()
            pending = self._state_ref(state, "pending")
            action = state.get("pending_action")
            if state.get("activation_in_progress") and pending is not None:
                return self._reject_interrupted_activation(state, pending)

            if pending is not None and action in {"update", "rollback"}:
                state["activation_in_progress"] = True
                self._write_state(state)
                try:
                    detected_version = self._probe_reference(pending)
                    if not self.versions_equal(detected_version, pending.version):
                        raise RuntimeError(
                            f"o pacote informou a versão {detected_version}, esperada {pending.version}"
                        )
                except Exception as error:
                    return self._reject_candidate(state, pending, error)

                old_active = self._state_ref(state, "active") or self._bundled_ref()
                state["active"] = asdict(pending)
                state["previous"] = asdict(old_active) if old_active != pending else state.get("previous")
                state["pending"] = None
                state["pending_action"] = None
                state["activation_in_progress"] = False
                kind = "updated" if action == "update" else "rolled_back"
                verb = "Atualização" if action == "update" else "Restauração"
                message = (
                    f"{verb} concluída: yt-dlp {pending.version} está ativo. "
                    f"A versão {old_active.version} foi mantida para recuperação."
                )
                state["last_event"] = self._event(
                    kind,
                    message,
                    version=pending.version,
                    previous_version=old_active.version,
                )
                if action == "update":
                    state["rejected_version"] = None
                self._write_state(state)
                self._garbage_collect(state)
                return ActivationResult(
                    active_version=pending.version,
                    changed=True,
                    action=action,
                    message=message,
                )

            active = self._state_ref(state, "active") or self._bundled_ref()
            try:
                version = self._probe_reference(active)
                return ActivationResult(active_version=version)
            except Exception as error:
                return self._recover_broken_active(state, active, error)

    def _reject_interrupted_activation(
        self,
        state: dict[str, Any],
        candidate: _ComponentRef,
    ) -> ActivationResult:
        error = RuntimeError("a ativação anterior foi interrompida antes da validação")
        return self._reject_candidate(state, candidate, error)

    def _reject_candidate(
        self,
        state: dict[str, Any],
        candidate: _ComponentRef,
        error: Exception,
    ) -> ActivationResult:
        state["activation_in_progress"] = False
        state["pending"] = None
        state["pending_action"] = None
        state["rejected_version"] = candidate.version
        active = self._state_ref(state, "active") or self._bundled_ref()
        if self._state_ref(state, "previous") == candidate:
            state["previous"] = None
        recovered, recovered_version = self._first_working_reference(
            active,
            self._state_ref(state, "previous"),
            self._bundled_ref(),
        )
        state["active"] = asdict(recovered)
        if recovered != active:
            state["previous"] = None
        detail = self._safe_error(error)
        message = (
            f"A versão {candidate.version} não pôde ser ativada ({detail}). "
            f"A versão {recovered_version} foi restaurada automaticamente."
        )
        state["last_event"] = self._event(
            "automatic_rollback",
            message,
            version=candidate.version,
            restored_version=recovered_version,
        )
        self._write_state(state)
        self._garbage_collect(state)
        LOGGER.warning(message)
        return ActivationResult(
            active_version=recovered_version,
            automatic_rollback=True,
            action="automatic_rollback",
            message=message,
        )

    def _recover_broken_active(
        self,
        state: dict[str, Any],
        active: _ComponentRef,
        error: Exception,
    ) -> ActivationResult:
        recovered, recovered_version = self._first_working_reference(
            self._state_ref(state, "previous"),
            self._bundled_ref(),
            exclude={active},
        )
        state["active"] = asdict(recovered)
        state["previous"] = None
        state["rejected_version"] = active.version
        detail = self._safe_error(error)
        message = (
            f"A versão ativa {active.version} falhou na validação ({detail}). "
            f"A versão {recovered_version} foi restaurada automaticamente."
        )
        state["last_event"] = self._event(
            "automatic_rollback",
            message,
            version=active.version,
            restored_version=recovered_version,
        )
        self._write_state(state)
        self._garbage_collect(state)
        LOGGER.warning(message)
        return ActivationResult(
            active_version=recovered_version,
            changed=True,
            automatic_rollback=True,
            action="automatic_rollback",
            message=message,
        )

    def _first_working_reference(
        self,
        *references: _ComponentRef | None,
        exclude: set[_ComponentRef] | None = None,
    ) -> tuple[_ComponentRef, str]:
        attempted: set[_ComponentRef] = set(exclude or set())
        errors: list[str] = []
        for reference in references:
            if reference is None or reference in attempted or not self._reference_available(reference):
                continue
            attempted.add(reference)
            try:
                return reference, self._probe_reference(reference)
            except Exception as error:
                errors.append(f"{reference.version}: {self._safe_error(error)}")
        joined = "; ".join(errors) or "nenhuma versão utilizável encontrada"
        raise RuntimeError(f"Não foi possível iniciar o yt-dlp: {joined}")

    def _probe_reference(self, reference: _ComponentRef) -> str:
        """Probe untrusted component code in a disposable process with a hard timeout."""
        result_path = self.root / f".yt-dlp-probe-{uuid.uuid4().hex}.json"
        payload = json.dumps(
            {
                "root": str(self.root.resolve()),
                "reference": asdict(reference),
                "bundled_version": self._detect_bundled_version(),
                "bundled_path": str(self._bundled_path) if self._bundled_path else None,
                "result_path": str(result_path.resolve()),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if getattr(sys, "frozen", False):
            command = [sys.executable, _PROBE_ARGUMENT, payload]
        else:
            command = [
                sys.executable,
                "-m",
                "mediadownloader.main",
                _PROBE_ARGUMENT,
                payload,
            ]
        options: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": _PROBE_TIMEOUT_SECONDS,
            "check": False,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            try:
                completed = subprocess.run(command, **options)  # noqa: S603
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    f"a validação excedeu {_PROBE_TIMEOUT_SECONDS} segundos"
                ) from error
            try:
                candidate = json.loads(result_path.read_text(encoding="utf-8"))
                report = candidate if isinstance(candidate, dict) else None
            except (OSError, json.JSONDecodeError):
                report = None
        finally:
            result_path.unlink(missing_ok=True)
        if completed.returncode != 0 or not report or report.get("ok") is not True:
            detail = report.get("error") if report else completed.stderr.strip()
            raise RuntimeError(str(detail or f"validação encerrou com código {completed.returncode}"))
        detected = str(report.get("version") or "")
        if not self.versions_equal(detected, reference.version):
            raise RuntimeError(f"versão validada {detected or 'desconhecida'}; esperada {reference.version}")
        self._select_reference(reference)
        return detected

    def _select_reference(self, reference: _ComponentRef) -> Path | None:
        self._clear_ytdlp_modules()
        self._remove_component_paths()
        location = self._reference_path(reference)
        if location is not None:
            sys.path.insert(0, str(location))
        importlib.invalidate_caches()
        return location

    def _probe_reference_in_process(self, reference: _ComponentRef) -> str:
        """Run only in the short-lived internal probe process."""
        location = self._select_reference(reference)

        package = importlib.import_module("yt_dlp")
        version_module = importlib.import_module("yt_dlp.version")
        utils_module = importlib.import_module("yt_dlp.utils")
        extractor_module = importlib.import_module("yt_dlp.extractor")
        detected = str(getattr(version_module, "__version__", ""))
        if not detected:
            raise RuntimeError("o pacote não informou sua versão")
        if not self.versions_equal(detected, reference.version):
            raise RuntimeError(f"versão carregada {detected}; esperada {reference.version}")
        if not callable(getattr(package, "YoutubeDL", None)):
            raise RuntimeError("API YoutubeDL ausente")
        if not isinstance(getattr(utils_module, "DownloadError", None), type):
            raise RuntimeError("API DownloadError ausente")
        generator = getattr(extractor_module, "gen_extractor_classes", None)
        if not callable(generator) or not generator():
            raise RuntimeError("catálogo de extractors indisponível")

        origin = Path(str(getattr(package, "__file__", ""))).resolve()
        if reference.source == "local":
            if location is None or not self._is_relative_to(origin, location.resolve()):
                raise RuntimeError("a versão local não foi carregada do diretório selecionado")
        elif self._is_relative_to(origin, self.versions_dir.resolve()):
            raise RuntimeError("a versão incluída foi substituída por um componente local")

        instance = package.YoutubeDL({"quiet": True, "no_warnings": True, "simulate": True})
        close = getattr(instance, "close", None)
        if callable(close):
            close()
        return detected

    def _pypi_payload(self, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            PYPI_URL,
            headers={"Accept": "application/json", "User-Agent": "MediaDownloader/1.1"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict):
            raise ValueError("Resposta inválida do índice do PyPI.")
        if not payload["info"].get("version") or not isinstance(payload.get("urls"), list):
            raise ValueError("O índice do PyPI não informou uma versão utilizável.")
        return payload

    @staticmethod
    def _select_wheel(payload: dict[str, Any]) -> dict[str, Any]:
        wheel = next(
            (
                item
                for item in payload["urls"]
                if isinstance(item, dict)
                and item.get("packagetype") == "bdist_wheel"
                and str(item.get("filename", "")).endswith("py3-none-any.whl")
            ),
            None,
        )
        if wheel is None:
            raise ValueError("O PyPI não forneceu o wheel universal esperado para o yt-dlp.")
        filename = str(wheel.get("filename") or "")
        if Path(filename).name != filename:
            raise ValueError("O índice do PyPI forneceu um nome de pacote inválido.")
        return wheel

    def _download_and_stage_wheel(
        self,
        *,
        wheel: dict[str, Any],
        expected_version: str,
        expected_digest: str,
        timeout: int,
    ) -> _ComponentRef:
        url = str(wheel.get("url") or "")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_FILE_HOSTS:
            raise ValueError("O pacote yt-dlp não aponta para um host HTTPS autorizado do PyPI.")

        self.versions_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".yt-dlp-staging-", dir=self.versions_dir
        ) as temporary:
            temporary_path = Path(temporary)
            archive = temporary_path / str(wheel["filename"])
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "MediaDownloader/1.1"},
            )
            digest = hashlib.sha256()
            total = 0
            with urllib.request.urlopen(request, timeout=timeout) as response, archive.open("wb") as output:  # noqa: S310
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_WHEEL_BYTES:
                        raise ValueError("O pacote yt-dlp excede o limite de tamanho permitido.")
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest().lower() != expected_digest:
                raise ValueError("Falha na verificação SHA-256 do pacote yt-dlp.")

            extracted = temporary_path / "package"
            extracted.mkdir()
            self._safe_extract(archive, extracted)
            self._validate_wheel_metadata(extracted, expected_version)
            detected = self._validate_package_tree(extracted, expected_version)
            directory_name = f"{self._version_slug(detected)}-{expected_digest[:12]}"
            destination = self.versions_dir / directory_name
            if destination.exists():
                self._validate_wheel_metadata(destination, expected_version)
                self._validate_package_tree(destination, expected_version)
            else:
                extracted.replace(destination)
        return _ComponentRef("local", detected, directory_name)

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        destination_root = destination.resolve()
        unpacked = 0
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                relative = Path(member.filename.replace("\\", "/"))
                mode = member.external_attr >> 16
                unpacked += max(0, member.file_size)
                if (
                    relative.is_absolute()
                    or bool(relative.drive)
                    or ".." in relative.parts
                    or stat.S_ISLNK(mode)
                    or unpacked > MAX_UNPACKED_BYTES
                ):
                    raise ValueError("O wheel yt-dlp contém uma estrutura de arquivos insegura.")
                target = (destination / relative).resolve()
                if not UpdateService._is_relative_to(target, destination_root):
                    raise ValueError("O wheel yt-dlp tentou gravar fora da área temporária.")
            package.extractall(destination)

    @staticmethod
    def _validate_package_tree(root: Path, expected_version: str) -> str:
        package = root / "yt_dlp"
        if not (package / "__init__.py").is_file() or not (package / "version.py").is_file():
            raise ValueError("O wheel não contém um pacote yt_dlp completo.")
        detected = UpdateService._directory_version(root)
        if not UpdateService.versions_equal(detected, expected_version):
            raise ValueError(
                f"O wheel contém a versão {detected or 'desconhecida'}, esperada {expected_version}."
            )
        for source in package.rglob("*.py"):
            try:
                with tokenize.open(source) as handle:
                    compile(handle.read(), str(source), "exec")
            except (OSError, SyntaxError, UnicodeError) as error:
                raise ValueError(f"Arquivo Python inválido no wheel: {source.name}.") from error
        return detected

    @staticmethod
    def _validate_wheel_metadata(root: Path, expected_version: str) -> None:
        """Reject updates whose runtime or default dependencies are not bundled."""
        matches: list[tuple[Path, Any]] = []
        for metadata_path in root.glob("*.dist-info/METADATA"):
            try:
                metadata = email.parser.Parser().parsestr(
                    metadata_path.read_text(encoding="utf-8", errors="strict")
                )
            except (OSError, UnicodeError) as error:
                raise ValueError("O wheel contém metadados inválidos.") from error
            if canonicalize_name(str(metadata.get("Name") or "")) == "yt-dlp":
                matches.append((metadata_path, metadata))
        if len(matches) != 1:
            raise ValueError("O wheel não contém metadados únicos e válidos do yt-dlp.")

        _metadata_path, metadata = matches[0]
        metadata_version = str(metadata.get("Version") or "")
        if not UpdateService.versions_equal(metadata_version, expected_version):
            raise ValueError(
                f"Os metadados do wheel informam a versão {metadata_version or 'desconhecida'}, "
                f"esperada {expected_version}."
            )
        requires_python = str(metadata.get("Requires-Python") or "").strip()
        if requires_python:
            UpdateService._validate_python_requirement(requires_python)

        environment = default_environment()
        for raw_requirement in metadata.get_all("Requires-Dist", []):
            try:
                requirement = Requirement(raw_requirement)
                base_environment = {**environment, "extra": ""}
                default_environment_values = {**environment, "extra": "default"}
                applies = requirement.marker is None or requirement.marker.evaluate(
                    base_environment
                ) or requirement.marker.evaluate(default_environment_values)
            except Exception as error:
                # Requirement marker evaluation can fail for malformed future metadata.
                raise ValueError(
                    f"O wheel contém uma dependência inválida: {raw_requirement}."
                ) from error
            if not applies:
                continue
            try:
                installed = importlib.metadata.version(requirement.name)
            except importlib.metadata.PackageNotFoundError as error:
                raise ValueError(
                    f"A atualização exige {requirement.name}, que não está incluído nesta versão do aplicativo."
                ) from error
            if requirement.specifier and not requirement.specifier.contains(
                installed, prereleases=True
            ):
                raise ValueError(
                    f"A atualização exige {requirement.name}{requirement.specifier}, "
                    f"mas o aplicativo inclui {installed}."
                )

    @staticmethod
    def _validate_python_requirement(requirement: str) -> None:
        try:
            specifier = SpecifierSet(requirement)
        except InvalidSpecifier as error:
            raise ValueError("O wheel informa uma versão de Python inválida.") from error
        current = Version(".".join(str(part) for part in sys.version_info[:3]))
        if not specifier.contains(current, prereleases=True):
            raise ValueError(
                f"A atualização exige Python {requirement}; este aplicativo usa Python {current}."
            )

    @staticmethod
    def _directory_version(root: Path) -> str:
        version_file = root / "yt_dlp" / "version.py"
        try:
            tree = ast.parse(version_file.read_text(encoding="utf-8"), filename=str(version_file))
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    value = node.value
                    if (
                        any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets)
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        return value.value
        except (OSError, SyntaxError):
            pass
        for metadata in root.glob("*.dist-info/METADATA"):
            try:
                match = re.search(
                    r"(?mi)^Version:\s*([^\s]+)\s*$",
                    metadata.read_text(encoding="utf-8", errors="replace"),
                )
                if match:
                    return match.group(1)
            except OSError:
                pass
        return ""

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                value = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(value, dict) and value.get("schema") == STATE_SCHEMA:
                    return self._normalize_state(value)
            except (OSError, json.JSONDecodeError, TypeError):
                LOGGER.warning("Estado de atualização do yt-dlp inválido; reconstruindo.")
            invalid = self.state_path.with_name("yt-dlp-state.invalid.json")
            try:
                os.replace(self.state_path, invalid)
            except OSError:
                pass
        state = self._migrate_legacy_state()
        self._write_state(state)
        return state

    def _normalize_state(self, value: dict[str, Any]) -> dict[str, Any]:
        bundled = self._bundled_ref()

        def reconcile(reference: _ComponentRef | None) -> _ComponentRef | None:
            return bundled if reference is not None and reference.source == "bundled" else reference

        active = reconcile(_ComponentRef.from_value(value.get("active"))) or bundled
        previous = reconcile(_ComponentRef.from_value(value.get("previous")))
        pending = reconcile(_ComponentRef.from_value(value.get("pending")))
        if previous == active:
            previous = None
        action = value.get("pending_action") if value.get("pending_action") in {"update", "rollback"} else None
        if pending is None:
            action = None
        return {
            "schema": STATE_SCHEMA,
            "active": asdict(active),
            "previous": asdict(previous) if previous else None,
            "pending": asdict(pending) if pending else None,
            "pending_action": action,
            "activation_in_progress": bool(value.get("activation_in_progress")),
            "rejected_version": value.get("rejected_version") if isinstance(value.get("rejected_version"), str) else None,
            "last_event": value.get("last_event") if isinstance(value.get("last_event"), dict) else None,
        }

    def _migrate_legacy_state(self) -> dict[str, Any]:
        bundled = self._bundled_ref()
        state: dict[str, Any] = {
            "schema": STATE_SCHEMA,
            "active": asdict(bundled),
            "previous": None,
            "pending": None,
            "pending_action": None,
            "activation_in_progress": False,
            "rejected_version": None,
            "last_event": None,
        }
        legacy_active = self.root / "yt-dlp"
        legacy_previous = self.root / "yt-dlp-old"
        legacy_pending = self.root / "yt-dlp-new"
        active = self._adopt_legacy_directory(legacy_active, "legacy-active")
        previous = self._adopt_legacy_directory(legacy_previous, "legacy-previous")
        pending = self._adopt_legacy_directory(legacy_pending, "legacy-pending")
        if active is not None:
            state["active"] = asdict(active)
            state["previous"] = asdict(previous or bundled)
            state["last_event"] = self._event(
                "legacy_migrated",
                f"Componente yt-dlp {active.version} migrado para o armazenamento seguro.",
            )
        if pending is not None:
            state["pending"] = asdict(pending)
            state["pending_action"] = "update"
        return state

    def _adopt_legacy_directory(self, source: Path, suffix: str) -> _ComponentRef | None:
        if not source.is_dir():
            return None
        version = self._directory_version(source)
        if not version:
            shutil.rmtree(source, ignore_errors=True)
            return None
        destination = self.versions_dir / f"{self._version_slug(version)}-{suffix}"
        if destination.exists():
            shutil.rmtree(source, ignore_errors=True)
        else:
            source.replace(destination)
        return _ComponentRef("local", version, destination.name)

    def _write_state(self, state: dict[str, Any]) -> None:
        state = self._normalize_state(state)
        temporary = self.state_path.with_name(f".{self.state_path.name}.{os.getpid()}.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.state_path)

    def _garbage_collect(self, state: dict[str, Any]) -> None:
        referenced = {
            reference.path
            for key in ("active", "previous", "pending")
            if (reference := self._state_ref(state, key)) is not None
            and reference.source == "local"
            and reference.path
        }
        for child in self.versions_dir.iterdir():
            if child.is_dir() and not child.name.startswith(".") and child.name not in referenced:
                shutil.rmtree(child, ignore_errors=True)

    def _bundled_ref(self) -> _ComponentRef:
        return _ComponentRef("bundled", self._detect_bundled_version())

    def _detect_bundled_version(self) -> str:
        if self._bundled_version_override:
            return self._bundled_version_override
        return _BUNDLED_YTDLP_VERSION

    @staticmethod
    def _state_ref(state: dict[str, Any], key: str) -> _ComponentRef | None:
        return _ComponentRef.from_value(state.get(key))

    def _reference_path(self, reference: _ComponentRef) -> Path | None:
        if reference.source == "bundled":
            return self._bundled_path
        if not reference.path or Path(reference.path).name != reference.path:
            raise RuntimeError("Referência local do yt-dlp inválida.")
        path = (self.versions_dir / reference.path).resolve()
        if not self._is_relative_to(path, self.versions_dir.resolve()):
            raise RuntimeError("Referência local do yt-dlp fora do diretório permitido.")
        if not path.is_dir():
            raise RuntimeError(f"Arquivos da versão {reference.version} não foram encontrados.")
        return path

    def _reference_available(self, reference: _ComponentRef) -> bool:
        if reference.source == "bundled":
            bundled = self._detect_bundled_version()
            return bundled != "não instalado" and self.versions_equal(reference.version, bundled)
        try:
            path = self._reference_path(reference)
            return path is not None and self._directory_version(path) == reference.version
        except RuntimeError:
            return False

    def _remove_component_paths(self) -> None:
        versions = self.versions_dir.resolve()
        bundled = self._bundled_path
        retained: list[str] = []
        for entry in sys.path:
            try:
                resolved = Path(entry).resolve()
                if self._is_relative_to(resolved, versions):
                    continue
                if bundled is not None and resolved == bundled:
                    continue
            except (OSError, TypeError):
                pass
            retained.append(entry)
        sys.path[:] = retained

    @staticmethod
    def _clear_ytdlp_modules() -> None:
        for name in [name for name in sys.modules if name == "yt_dlp" or name.startswith("yt_dlp.")]:
            sys.modules.pop(name, None)

    @staticmethod
    def _event(kind: str, message: str, **details: object) -> dict[str, object]:
        return {
            "kind": kind,
            "message": message,
            "at": datetime.now(UTC).isoformat(),
            **details,
        }

    @staticmethod
    def _safe_error(error: BaseException) -> str:
        value = str(error).strip().splitlines()[-1] if str(error).strip() else error.__class__.__name__
        return value[:240]

    @staticmethod
    def _version_slug(version: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._+-]", "-", version).strip(".-")
        return value or "unknown"

    @staticmethod
    def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
        tokens = re.findall(r"\d+|[A-Za-z]+", version)
        return tuple(
            (0, int(token)) if token.isdigit() else (1, token.lower())
            for token in tokens
        )

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


def activate_updated_ytdlp() -> ActivationResult:
    """Select and probe the user-local component before the rest of the app imports it."""
    return UpdateService().activate()


def run_internal_ytdlp_probe(payload_text: str) -> int:
    """Internal child-process entry point; never exposed as an end-user command."""
    report: dict[str, object]
    result_path: Path | None = None
    try:
        payload = json.loads(payload_text)
        if not isinstance(payload, dict) or not isinstance(payload.get("root"), str):
            raise ValueError("solicitação de validação inválida")
        root = Path(payload["root"]).resolve()
        result_path_value = payload.get("result_path")
        if not isinstance(result_path_value, str):
            raise ValueError("destino da validação inválido")
        result_path = Path(result_path_value).resolve()
        if (
            result_path.parent != root
            or not result_path.name.startswith(".yt-dlp-probe-")
            or result_path.suffix != ".json"
        ):
            raise ValueError("destino da validação fora da área permitida")
        reference = _ComponentRef.from_value(payload.get("reference"))
        if reference is None:
            raise ValueError("referência de componente inválida")
        bundled_version = payload.get("bundled_version")
        bundled_path_value = payload.get("bundled_path")
        if not isinstance(bundled_version, str) or not bundled_version:
            raise ValueError("versão incluída inválida")
        if bundled_path_value is not None and not isinstance(bundled_path_value, str):
            raise ValueError("caminho incluído inválido")
        service = UpdateService(
            root,
            bundled_version=bundled_version,
            bundled_path=Path(bundled_path_value) if bundled_path_value else None,
        )
        version = service._probe_reference_in_process(reference)
        report = {"ok": True, "version": version}
        exit_code = 0
    except BaseException as error:  # The child must turn even SystemExit into a failed probe.
        report = {
            "ok": False,
            "error": UpdateService._safe_error(error),
            "type": error.__class__.__name__,
        }
        exit_code = 2
    if result_path is not None:
        result_path.write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )
    return exit_code

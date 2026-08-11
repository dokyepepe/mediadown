"""Download queue model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class DownloadStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    DOWNLOADING_VIDEO = "downloading_video"
    DOWNLOADING_AUDIO = "downloading_audio"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    CONVERTING = "converting"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {self.COMPLETED, self.ERROR, self.CANCELLED}

    @property
    def label(self) -> str:
        return {
            self.QUEUED: "Na fila",
            self.PREPARING: "Preparando",
            self.DOWNLOADING_VIDEO: "Baixando vídeo",
            self.DOWNLOADING_AUDIO: "Baixando áudio",
            self.DOWNLOADING: "Baixando",
            self.MERGING: "Mesclando",
            self.CONVERTING: "Convertendo",
            self.FINALIZING: "Finalizando",
            self.COMPLETED: "Concluído",
            self.ERROR: "Erro",
            self.CANCELLED: "Cancelado",
        }[self]


class MediaType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(slots=True)
class DownloadItem:
    url: str
    title: str
    output_path: str
    media_type: MediaType = MediaType.VIDEO
    format: str = "Automático"
    quality: str = "Automática"
    author: str = ""
    thumbnail: str = ""
    platform: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed: float | None = None
    eta: int | None = None
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    error: str = ""
    technical_error: str = ""
    final_file: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        result["media_type"] = self.media_type.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadItem":
        values = dict(data)
        values["status"] = DownloadStatus(values.get("status", DownloadStatus.QUEUED))
        values["media_type"] = MediaType(values.get("media_type", MediaType.VIDEO))
        return cls(**values)


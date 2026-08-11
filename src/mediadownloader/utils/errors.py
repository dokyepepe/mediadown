"""Central mapping from technical failures to safe user-facing messages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FriendlyError(Exception):
    message: str
    details: str = ""
    code: str = "unknown"

    def __str__(self) -> str:
        return self.message


def classify_error(error: BaseException | str) -> FriendlyError:
    details = str(error)
    text = details.lower()
    mappings = (
        (("drm", "widevine", "protected content"), "Este conteúdo parece utilizar proteção DRM e não pode ser baixado por este aplicativo.", "drm"),
        (("private video", "login required", "sign in", "authentication"), "Este conteúdo requer acesso. Verifique sua conta ou configuração de cookies.", "authentication"),
        (("geo", "not available in your country"), "Este conteúdo possui restrição geográfica.", "geo"),
        (("unsupported url", "no suitable extractor"), "Não foi possível encontrar mídia compatível neste endereço.", "unsupported"),
        (("video unavailable", "removed", "not available"), "O conteúdo foi removido ou não está disponível.", "unavailable"),
        (("no space left", "disk full"), "Não há espaço suficiente no disco.", "disk_full"),
        (("permission denied", "access is denied"), "Permissão negada ao gravar o arquivo.", "permission"),
        (("ffmpeg", "ffprobe"), "O FFmpeg não conseguiu processar esta mídia.", "ffmpeg"),
        (("timed out", "network is unreachable", "temporary failure", "connection"), "Não foi possível conectar ao serviço. Verifique sua conexão.", "network"),
        (("requested format is not available",), "O formato selecionado não está disponível para esta mídia.", "format"),
    )
    for needles, message, code in mappings:
        if any(needle in text for needle in needles):
            return FriendlyError(message, details, code)
    return FriendlyError("Ocorreu um erro inesperado. Consulte os detalhes ou o log.", details)


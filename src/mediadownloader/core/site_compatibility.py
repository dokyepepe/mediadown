"""Per-site compatibility reference for Settings and the About page.

The mobile edition ships this as a static card. Here the same information is
enriched with a live probe of the installed yt-dlp extractors, so a user can
tell "this site is not supported at all" apart from "this site is supported but
needs your cookies". The probe never touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QCoreApplication

from mediadownloader.core.platform_catalog import PlatformInfo, supported_platforms


class SiteState(StrEnum):
    SUPPORTED = "supported"
    NEEDS_COOKIES = "needs_cookies"
    METADATA_ONLY = "metadata_only"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True, frozen=True)
class SiteRow:
    platform: PlatformInfo
    state: SiteState
    label: str
    description: str


# Sites where the public extractor only answers for logged-in or restricted
# content. Keys are the ``PlatformInfo.extractor_fragment`` values.
_COOKIE_NOTES = {
    "youtube": "Vídeos privados, membros e com restrição de idade exigem os cookies da sua conta.",
    "tiktok": "Alguns perfis e vídeos só são lidos com os cookies da sua conta.",
    "instagram": "Conteúdo privado, Reels e stories dependem do seu login.",
    "facebook": "Vídeos de grupos e páginas privadas dependem do seu login.",
    "twitter": "Apenas posts públicos são lidos; vídeos de contas privadas exigem login.",
    "soundcloud": "Faixas e playlists privadas exigem o seu login.",
    "reddit": "Post em subreddit privado exige o seu login.",
}


def _tr(message: str) -> str:
    return QCoreApplication.translate("SiteCompatibility", message)


def state_label(state: SiteState) -> str:
    return {
        SiteState.SUPPORTED: _tr("Suportado"),
        SiteState.NEEDS_COOKIES: _tr("Suportado com cookies"),
        SiteState.METADATA_ONLY: _tr("Metadados apenas"),
        SiteState.UNAVAILABLE: _tr("Indisponível"),
    }[state]


def state_for(platform: PlatformInfo, supported: bool) -> SiteState:
    if not supported:
        return SiteState.UNAVAILABLE
    if platform.native_integration:
        return SiteState.METADATA_ONLY
    if platform.extractor_fragment in _COOKIE_NOTES:
        return SiteState.NEEDS_COOKIES
    return SiteState.SUPPORTED


def _description(platform: PlatformInfo, state: SiteState) -> str:
    if state is SiteState.UNAVAILABLE:
        return _tr(
            "O yt-dlp instalado não traz um extractor para este site. "
            "Atualize o componente para voltar a usá-lo."
        )
    if state is SiteState.METADATA_ONLY:
        return _tr(
            "Catálogo e playlists são lidos com o seu login, mas o áudio não é baixado."
        )
    if state is SiteState.NEEDS_COOKIES:
        return _tr(_COOKIE_NOTES[platform.extractor_fragment])
    return _tr(platform.description)


def rows() -> list[SiteRow]:
    """One row per advertised platform, resolved against the installed yt-dlp."""
    supported = {platform.extractor_fragment for platform in supported_platforms()}
    result: list[SiteRow] = []
    for platform in supported_platforms():
        state = state_for(platform, True)
        result.append(
            SiteRow(
                platform=platform,
                state=state,
                label=state_label(state),
                description=_description(platform, state),
            )
        )
    return result


def unavailable_platforms() -> list[PlatformInfo]:
    """Catalog entries the installed yt-dlp cannot handle, Spotify excluded."""
    from mediadownloader.core.platform_catalog import (  # noqa: PLC0415 - avoids a cycle
        PLATFORMS,
        extractor_names,
    )

    names = extractor_names()
    if not names:
        return []
    return [
        platform
        for platform in PLATFORMS
        if not platform.native_integration
        and not any(platform.extractor_fragment in name for name in names)
    ]


def summary() -> str:
    """One-line count for the Settings header, e.g. ``12 de 13 sites``."""
    rows_now = rows()
    missing = unavailable_platforms()
    text = _tr("{supported} sites prontos para usar").format(supported=len(rows_now))
    if missing:
        text = _tr("{supported} sites prontos, {missing} indisponíveis").format(
            supported=len(rows_now), missing=len(missing)
        )
    return text

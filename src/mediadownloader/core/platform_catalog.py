"""Curated platform presentation backed by the installed yt-dlp extractors."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(slots=True, frozen=True)
class PlatformInfo:
    name: str
    description: str
    extractor_fragment: str
    icon: str
    capabilities: str
    native_integration: bool = False


PLATFORMS = (
    PlatformInfo("YouTube", "Vídeos, Shorts, playlists e canais", "youtube", "video", "VÍDEO • ÁUDIO • PLAYLIST"),
    PlatformInfo("Vimeo", "Vídeos públicos, canais e álbuns", "vimeo", "video", "VÍDEO • ÁUDIO"),
    PlatformInfo("Twitch", "Clipes, transmissões e VODs disponíveis", "twitch", "video", "VÍDEO • LIVE"),
    PlatformInfo("SoundCloud", "Faixas, sets e playlists públicas", "soundcloud", "audio", "ÁUDIO • PLAYLIST"),
    PlatformInfo("Bandcamp", "Faixas, álbuns e páginas de artistas", "bandcamp", "audio", "ÁUDIO • ÁLBUM"),
    PlatformInfo("TikTok", "Vídeos e coleções acessíveis", "tiktok", "video", "VÍDEO"),
    PlatformInfo("Instagram", "Posts, Reels e stories acessíveis", "instagram", "video", "VÍDEO • IMAGEM"),
    PlatformInfo("Facebook", "Vídeos públicos e páginas compatíveis", "facebook", "video", "VÍDEO"),
    PlatformInfo("X / Twitter", "Vídeos incorporados em posts públicos", "twitter", "video", "VÍDEO"),
    PlatformInfo("Reddit", "Vídeos hospedados e posts compatíveis", "reddit", "video", "VÍDEO"),
    PlatformInfo("Dailymotion", "Vídeos, usuários e playlists", "dailymotion", "video", "VÍDEO • PLAYLIST"),
    PlatformInfo("PeerTube", "Instâncias e playlists federadas", "peertube", "globe", "VÍDEO • PLAYLIST"),
    PlatformInfo(
        "Spotify",
        "Metadados e playlists autorizadas, sem download direto",
        "",
        "audio",
        "METADADOS • PLAYLIST AUTORIZADA",
        True,
    ),
)


@lru_cache(maxsize=1)
def extractor_names() -> frozenset[str]:
    try:
        from yt_dlp.extractor import gen_extractor_classes

        return frozenset(
            str(getattr(extractor, "IE_NAME", "")).lower()
            for extractor in gen_extractor_classes()
            if getattr(extractor, "IE_NAME", "")
        )
    except Exception:
        return frozenset()


def extractor_count() -> int:
    return len(extractor_names())


def supported_platforms() -> tuple[PlatformInfo, ...]:
    names = extractor_names()
    if not names:
        return PLATFORMS
    return tuple(
        platform
        for platform in PLATFORMS
        if platform.native_integration
        or any(platform.extractor_fragment in name for name in names)
    )

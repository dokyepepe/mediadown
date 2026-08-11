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
    brand_background: str
    brand_accent: str
    logo_color: str = "#FFFFFF"
    native_integration: bool = False


PLATFORMS = (
    PlatformInfo("YouTube", "Vídeos, Shorts, playlists e canais", "youtube", "brands/youtube", "VÍDEO • ÁUDIO • PLAYLIST", "#FF0000", "#FF0000"),
    PlatformInfo("Vimeo", "Vídeos públicos, canais e álbuns", "vimeo", "brands/vimeo", "VÍDEO • ÁUDIO", "#1AB7EA", "#1AB7EA"),
    PlatformInfo("Twitch", "Clipes, transmissões e VODs disponíveis", "twitch", "brands/twitch", "VÍDEO • LIVE", "#9146FF", "#9146FF"),
    PlatformInfo("SoundCloud", "Faixas, sets e playlists públicas", "soundcloud", "brands/soundcloud", "ÁUDIO • PLAYLIST", "#FF5500", "#FF5500"),
    PlatformInfo("Bandcamp", "Faixas, álbuns e páginas de artistas", "bandcamp", "brands/bandcamp", "ÁUDIO • ÁLBUM", "#408294", "#408294"),
    PlatformInfo("TikTok", "Vídeos e coleções acessíveis", "tiktok", "brands/tiktok", "VÍDEO", "#111111", "#25F4EE"),
    PlatformInfo("Instagram", "Posts, Reels e stories acessíveis", "instagram", "brands/instagram", "VÍDEO • IMAGEM", "qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #FEDA75,stop:0.28 #FA7E1E,stop:0.55 #D62976,stop:0.78 #962FBF,stop:1 #4F5BD5)", "#FF0069"),
    PlatformInfo("Facebook", "Vídeos públicos e páginas compatíveis", "facebook", "brands/facebook", "VÍDEO", "#0866FF", "#0866FF"),
    PlatformInfo("X / Twitter", "Vídeos incorporados em posts públicos", "twitter", "brands/x", "VÍDEO", "#111111", "#65727C"),
    PlatformInfo("Reddit", "Vídeos hospedados e posts compatíveis", "reddit", "brands/reddit", "VÍDEO", "#FF4500", "#FF4500"),
    PlatformInfo("Dailymotion", "Vídeos, usuários e playlists", "dailymotion", "brands/dailymotion", "VÍDEO • PLAYLIST", "#101010", "#00AAFF"),
    PlatformInfo("PeerTube", "Instâncias e playlists federadas", "peertube", "brands/peertube", "VÍDEO • PLAYLIST", "#211F20", "#F1680D"),
    PlatformInfo(
        "Spotify",
        "Metadados e playlists autorizadas, sem download direto",
        "",
        "brands/spotify",
        "METADADOS • PLAYLIST AUTORIZADA",
        "#1ED760",
        "#1DB954",
        "#101010",
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

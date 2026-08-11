"""Input validation with conservative URL rules."""

from __future__ import annotations

from urllib.parse import urlparse


SPOTIFY_HOSTS = {"open.spotify.com", "play.spotify.com", "spotify.link"}


def is_valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc) and "." in parsed.netloc
    except (TypeError, ValueError):
        return False


def validate_url(value: str) -> tuple[bool, str]:
    if not value.strip():
        return False, "Insira uma URL."
    if not is_valid_url(value):
        return False, "Este endereço não parece ser uma URL válida."
    return True, ""


def is_spotify_url(value: str) -> bool:
    """Return whether a URL points to an official Spotify web host."""
    if not is_valid_url(value):
        return False
    try:
        return (urlparse(value.strip()).hostname or "").lower() in SPOTIFY_HOSTS
    except ValueError:
        return False

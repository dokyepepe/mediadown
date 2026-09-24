"""Per-site cookie profile resolution.

Profiles let the user attach a cookies.txt file to specific sites while the
global cookie source (file or browser) stays as the fallback for everything
else. Resolution is pure and independent of Qt so it can be tested and reused
by the engine and by the UI.
"""

from __future__ import annotations

from typing import Iterable, Mapping
from urllib.parse import urlsplit

CookieProfileDict = Mapping[str, object]


def host_of(url: str) -> str:
    """Normalized hostname of a URL, or "" when the URL carries no host.

    Unlike a bare scheme-less string, only URLs that include a host parse to a
    non-empty hostname, so ``://``-less inputs never match a profile.
    """
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_pattern(pattern: str) -> str:
    value = pattern.strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip(".")


def profile_matches(profile: CookieProfileDict, url: str) -> bool:
    """Whether a profile's site patterns cover the URL's host.

    A pattern like ``youtube.com`` also matches ``www.youtube.com`` and any
    subdomain (``m.youtube.com``). Specific patterns are matched only when the
    host equals the pattern or is a direct/subdomain of it.
    """
    host = host_of(url)
    if not host:
        return False
    patterns = profile.get("hosts") or []
    if isinstance(patterns, str):
        patterns = [patterns]
    for raw in patterns:
        pattern = _normalize_pattern(raw)
        if not pattern:
            continue
        if host == pattern or host.endswith(f".{pattern}"):
            return True
    return False


def matched_profile(profiles: Iterable[CookieProfileDict], url: str) -> CookieProfileDict | None:
    """First profile whose patterns cover the URL, or ``None``."""
    for profile in profiles:
        if not isinstance(profile, Mapping) or not profile.get("file"):
            continue
        if profile_matches(profile, url):
            return profile
    return None


def resolve_cookies(
    source: str,
    file: str,
    browser: str,
    profiles: Iterable[CookieProfileDict] | None,
    url: str,
) -> tuple[str, str]:
    """Pick the cookies to use for a URL: ``(cookies_file, cookies_browser)``.

    A matching per-site profile takes priority over the global source. Without a
    match the global ``source``/``file``/``browser`` behavior is preserved.
    """
    matched = matched_profile(profiles or [], url)
    if matched is not None:
        return str(matched["file"]), ""
    if source == "file":
        return file, ""
    if source == "browser":
        return "", browser
    return "", ""
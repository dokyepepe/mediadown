"""Helpers for reading one or many media URLs out of arbitrary text."""

from __future__ import annotations

import re

#: ``scheme://host`` with an optional path/query, stopping before trailing punctuation
#: that is far more common in shared text than in a real address.
URL_PATTERN = re.compile(
    r"""https?://[^\s<>"'`\\^{|}\[\]()]+""",
    re.IGNORECASE,
)

#: Characters people append to a link when they paste it into a chat or document.
_TRAILING_NOISE = ".,;:!?…'\"»”)]}>"


def clean_url(raw: str) -> str:
    """Strip the punctuation that follows a link in prose."""
    return raw.strip().rstrip(_TRAILING_NOISE)


def extract_urls(text: str, limit: int = 200) -> list[str]:
    """Every distinct media URL in ``text``, in the order it appears.

    Duplicates are dropped so pasting the same link twice queues it once, and
    ``limit`` keeps a huge paste from flooding the queue.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in URL_PATTERN.finditer(text or ""):
        url = clean_url(match.group(0))
        if not url or url in seen:
            continue
        seen.add(url)
        found.append(url)
        if len(found) >= limit:
            break
    return found

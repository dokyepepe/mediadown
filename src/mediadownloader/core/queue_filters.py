"""Pure search and filter rules for the downloads queue view.

Kept apart from the page so the same rules can be reused by tests and by any
future queue surface, and so the counts shown on the filter chips always come
from one implementation.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Iterable, Mapping

from mediadownloader.models import DownloadItem, DownloadStatus


class QueueFilter(StrEnum):
    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


#: Statuses each filter considers a match. ``FAILED`` deliberately groups
#: cancelled items too, because both mean "this did not finish and is not
#: running", which is what a user filtering on failures is looking for.
_FILTER_STATUSES: Mapping[QueueFilter, frozenset[DownloadStatus]] = {
    QueueFilter.ALL: frozenset(DownloadStatus),
    QueueFilter.ACTIVE: frozenset(DownloadStatus)
    - frozenset({DownloadStatus.COMPLETED, DownloadStatus.ERROR, DownloadStatus.CANCELLED}),
    QueueFilter.COMPLETED: frozenset({DownloadStatus.COMPLETED}),
    QueueFilter.FAILED: frozenset({DownloadStatus.ERROR, DownloadStatus.CANCELLED}),
}


def _fold(text: str) -> str:
    """Lowercase without accents, so ``video`` also finds ``Vídeo``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _matches_query(item: DownloadItem, needle: str) -> bool:
    haystack = " ".join(
        part
        for part in (item.title, item.author, item.platform, item.format, item.url, item.error)
        if part
    )
    return needle in _fold(haystack)


def filter_items(
    items: Iterable[DownloadItem],
    query: str = "",
    mode: QueueFilter = QueueFilter.ALL,
) -> list[DownloadItem]:
    """Apply the status filter first, then the free-text query.

    A query narrows whatever the filter already selected, so combining the two
    never widens the result set by accident.
    """
    statuses = _FILTER_STATUSES.get(QueueFilter(mode), frozenset(DownloadStatus))
    needle = _fold(query.strip())
    result = [item for item in items if item.status in statuses]
    if needle:
        result = [item for item in result if _matches_query(item, needle)]
    return result


def filter_counts(items: Iterable[DownloadItem]) -> dict[QueueFilter, int]:
    """Count items per filter, for the chip labels."""
    collected = list(items)
    return {mode: len(filter_items(collected, mode=mode)) for mode in QueueFilter}

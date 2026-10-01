from __future__ import annotations

from mediadownloader.core.queue_filters import QueueFilter, filter_counts, filter_items
from mediadownloader.models import DownloadItem, DownloadStatus


def _item(status: DownloadStatus, **kwargs) -> DownloadItem:
    return DownloadItem(
        url=kwargs.pop("url", "https://example.com/a"),
        title=kwargs.pop("title", "Título"),
        author=kwargs.pop("author", "Autor"),
        output_path=kwargs.pop("output_path", "/tmp"),
        platform=kwargs.pop("platform", "youtube"),
        status=status,
        **kwargs,
    )


ALL = [
    _item(DownloadStatus.COMPLETED, title="Receita de bolo"),
    _item(DownloadStatus.DOWNLOADING, title="Musica ao vivo"),
    _item(DownloadStatus.QUEUED, title="receita de bolo again"),
    _item(DownloadStatus.ERROR, title="Vídeo perdido", error="403 Forbidden"),
    _item(DownloadStatus.CANCELLED, title="Cancelado"),
    _item(DownloadStatus.PAUSED, title="Pausado agora"),
]


def test_filter_items_by_status():
    assert len(filter_items(ALL, mode=QueueFilter.ALL)) == len(ALL)
    assert len(filter_items(ALL, mode=QueueFilter.COMPLETED)) == 1
    assert len(filter_items(ALL, mode=QueueFilter.FAILED)) == 2
    # Everything not finished yet: queued, paused and working.
    assert len(filter_items(ALL, mode=QueueFilter.ACTIVE)) == 3


def test_filter_items_by_text_ignores_case_and_accents():
    found = filter_items(ALL, "bolo")
    assert [item.title for item in found] == ["Receita de bolo", "receita de bolo again"]

    assert [item.title for item in filter_items(ALL, "VIDEO")] == ["Vídeo perdido"]
    assert filter_items(ALL, "inexistente") == []


def test_a_query_narrows_the_active_filter():
    found = filter_items(ALL, "bolo", QueueFilter.ACTIVE)
    assert [item.title for item in found] == ["receita de bolo again"]


def test_search_also_covers_url_author_and_error_text():
    assert len(filter_items(ALL, "example.com")) == len(ALL)
    assert len(filter_items(ALL, "403")) == 1
    assert len(filter_items(ALL, "youtube")) == len(ALL)


def test_filter_counts_matches_each_bucket():
    counts = filter_counts(ALL)
    assert counts[QueueFilter.ALL] == 6
    assert counts[QueueFilter.ACTIVE] == 3
    assert counts[QueueFilter.COMPLETED] == 1
    assert counts[QueueFilter.FAILED] == 2


def test_active_status_property_is_narrower_than_the_active_filter():
    # "Working right now" is what the queue's active count means; the ACTIVE
    # filter additionally shows items waiting or paused.
    assert DownloadStatus.DOWNLOADING.active is True
    assert DownloadStatus.QUEUED.active is False
    assert DownloadStatus.PAUSED.active is False
    assert DownloadStatus.QUEUED in {
        item.status for item in filter_items(ALL, mode=QueueFilter.ACTIVE)
    }

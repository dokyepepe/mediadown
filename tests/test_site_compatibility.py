from __future__ import annotations

from mediadownloader.core.platform_catalog import PLATFORMS, PlatformInfo
from mediadownloader.core.site_compatibility import (
    SiteState, rows, state_for, state_label, summary, unavailable_platforms,
)


def test_every_catalog_entry_gets_a_row_with_a_label():
    result = rows()
    assert [row.platform.name for row in result]
    for row in result:
        assert row.label
        assert row.description
        assert row.state is not SiteState.UNAVAILABLE


def test_sites_needing_an_account_are_flagged():
    assert state_for(_platform("youtube", "youtube"), True) is SiteState.NEEDS_COOKIES
    assert state_for(_platform("tiktok", "tiktok"), True) is SiteState.NEEDS_COOKIES
    assert state_for(_platform("vimeo", "vimeo"), True) is SiteState.SUPPORTED


def test_spotify_is_metadata_only_rather_than_supported():
    spotify = next(item for item in PLATFORMS if item.name == "Spotify")
    assert state_for(spotify, True) is SiteState.METADATA_ONLY
    assert state_label(SiteState.METADATA_ONLY) == "Metadados apenas"


def test_an_unsupported_platform_is_reported_unavailable():
    platform = _platform("inexistente", "inexistente")
    assert state_for(platform, False) is SiteState.UNAVAILABLE
    assert state_label(SiteState.UNAVAILABLE) == "Indisponível"


def test_unavailable_platforms_never_lists_spotify():
    assert all(item.native_integration for item in unavailable_platforms())


def test_summary_mentions_the_ready_count():
    text = summary()
    assert str(len(rows())) in text


def _platform(name: str, fragment: str) -> PlatformInfo:
    return PlatformInfo(
        name=name,
        description="",
        extractor_fragment=fragment,
        icon="",
        capabilities="",
        brand_background="#000000",
        brand_accent="#000000",
    )

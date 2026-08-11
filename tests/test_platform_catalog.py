from pathlib import Path
from xml.etree import ElementTree

from mediadownloader.core.platform_catalog import extractor_count, supported_platforms
from mediadownloader.utils.paths import asset_path


def test_catalog_is_backed_by_installed_extractors():
    platforms = supported_platforms()
    assert extractor_count() > 100
    assert {platform.name for platform in platforms} >= {"YouTube", "Vimeo", "SoundCloud", "Spotify"}


def test_catalog_icons_are_valid_svg_assets():
    for platform in supported_platforms():
        icon = asset_path("icons", f"{platform.icon}.svg")
        assert icon.exists(), platform.name
        assert ElementTree.parse(icon).getroot().tag.endswith("svg")

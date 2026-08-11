from mediadownloader.utils.formatting import format_bytes, format_eta


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(None) == "—"


def test_format_eta():
    assert format_eta(14) == "00:14"
    assert format_eta(3661) == "01:01:01"
    assert format_eta(None) == "—"


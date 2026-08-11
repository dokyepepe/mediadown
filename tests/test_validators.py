from mediadownloader.utils.validators import is_valid_url, validate_url


def test_valid_http_urls():
    assert is_valid_url("https://example.com/video?id=1")
    assert is_valid_url("http://sub.example.org/a")


def test_invalid_urls_have_friendly_message():
    assert validate_url("") == (False, "Insira uma URL.")
    assert not is_valid_url("javascript:alert(1)")
    assert not validate_url("example.com")[0]


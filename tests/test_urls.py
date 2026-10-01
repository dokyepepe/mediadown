from mediadownloader.utils.urls import clean_url, extract_urls


def test_extracts_every_address_from_shared_text() -> None:
    text = (
        "Olha isso: https://www.youtube.com/watch?v=abc e depois\n"
        "https://youtu.be/xyz,\nalso https://vimeo.com/12345."
    )

    assert extract_urls(text) == [
        "https://www.youtube.com/watch?v=abc",
        "https://youtu.be/xyz",
        "https://vimeo.com/12345",
    ]


def test_ignores_duplicates_keeping_the_first_position() -> None:
    text = "https://a.example/1 https://b.example/2 https://a.example/1"

    assert extract_urls(text) == ["https://a.example/1", "https://b.example/2"]


def test_strips_punctuation_added_by_chat_apps() -> None:
    assert clean_url("https://a.example/1.") == "https://a.example/1"
    assert clean_url("https://a.example/1)") == "https://a.example/1"


def test_returns_nothing_for_text_without_links() -> None:
    assert extract_urls("sem link aqui, só texto.") == []
    assert extract_urls("") == []


def test_respects_the_limit() -> None:
    text = "\n".join(f"https://a.example/{index}" for index in range(10))

    assert len(extract_urls(text, limit=3)) == 3

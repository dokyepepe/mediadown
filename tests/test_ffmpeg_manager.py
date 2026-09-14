"""Unit tests for FFmpegManager helpers used by the media preview."""

from __future__ import annotations

import os

from mediadownloader.core.ffmpeg_manager import _normalize_input_url


def test_normalize_https_url_is_unchanged() -> None:
    url = "https://cdn.example.com/video.mp4"
    assert _normalize_input_url(url) == url


def test_normalize_file_url_becomes_plain_path() -> None:
    value = _normalize_input_url("file:///C:/Users/test/pasta/audio.wav")
    assert not value.startswith("file://")
    assert value.endswith("audio.wav")
    if os.name == "nt":
        assert value.lower().replace("\\", "/") == "c:/users/test/pasta/audio.wav"
    else:
        assert value == "/C:/Users/test/pasta/audio.wav"


def test_normalize_file_url_with_spaces_decodes() -> None:
    value = _normalize_input_url("file:///C:/Temp/minha%20m%C3%BAsica.wav")
    assert value.endswith("minha música.wav")


def test_normalize_file_url_falls_back_on_garbage() -> None:
    value = _normalize_input_url("file:///")
    assert isinstance(value, str)
"""Unit tests for FFmpegManager helpers used by the media preview."""

from __future__ import annotations

import os
import subprocess
import threading

import pytest

from mediadownloader.core.ffmpeg_manager import (
    FFmpegManager,
    _header_args,
    _normalize_input_url,
)


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


def test_header_args_builds_crlf_value() -> None:
    args = _header_args({"User-Agent": "test", "Referer": "https://x/"})
    assert args == [
        "-headers",
        "User-Agent: test\r\nReferer: https://x/\r\n",
    ]
    assert _header_args({}) == []
    assert _header_args(None) == []


def _run(ffmpeg: FFmpegManager, arguments: list[str]) -> None:
    result = subprocess.run(
        arguments,
        capture_output=True,
        timeout=120,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-800:]


def test_render_preview_merges_separate_video_and_audio(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.m4a"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-an", str(video),
    ])
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:a", "aac", "-vn", str(audio),
    ])

    output = tmp_path / "merged.mkv"
    ffmpeg.render_preview(
        str(video),
        output,
        audio_filter="",
        duration=1.0,
        start_time=0.0,
        video_url=str(video),
        audio_url=str(audio),
    )

    assert output.exists() and output.stat().st_size > 0
    probe = subprocess.run(
        [
            str(ffmpeg.ffprobe), "-v", "error",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(output),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    codec_types = {line.strip() for line in probe.stdout.splitlines() if line.strip()}
    assert "video" in codec_types
    assert "audio" in codec_types


def test_duration_reads_the_length_of_a_file(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    audio = tmp_path / "audio.m4a"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:a", "aac", str(audio),
    ])

    assert ffmpeg.duration(audio) == pytest.approx(3.0, abs=0.2)


def test_duration_is_zero_without_ffprobe(tmp_path) -> None:
    ffmpeg = FFmpegManager(tmp_path)

    assert ffmpeg.duration(tmp_path / "qualquer.mp4") == 0.0


def test_post_process_trims_and_fades_replacing_the_original(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    source = tmp_path / "musica.mp3"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        str(source),
    ])

    edited = ffmpeg.post_process(
        source,
        audio_filter="afade=t=in:st=0:d=1,afade=t=out:st=8:d=1",
        start_seconds=2.0,
        duration_seconds=6.0,
        has_video=False,
    )

    assert edited == tmp_path / "musica.edited.m4a"
    assert edited.exists() and not source.exists()
    assert ffmpeg.duration(edited) == pytest.approx(6.0, abs=0.3)


def test_post_process_editor_profile_produces_mp4(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    source = tmp_path / "video.mkv"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(source),
    ])

    edited = ffmpeg.post_process(source, editor_compatible=True)

    assert edited.suffix == ".mp4"
    assert edited.exists()
    probe = subprocess.run(
        [
            str(ffmpeg.ffprobe), "-v", "error", "-show_entries",
            "stream=codec_name", "-of", "csv=p=0", str(edited),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    codecs = {line.strip() for line in probe.stdout.splitlines() if line.strip()}
    assert "h264" in codecs
    assert "aac" in codecs


def test_post_process_copies_streams_when_nothing_needs_reencoding(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    source = tmp_path / "copia.mp4"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", "-an", str(source),
    ])

    edited = ffmpeg.post_process(source)

    assert edited.exists()
    probe = subprocess.run(
        [
            str(ffmpeg.ffprobe), "-v", "error", "-show_entries",
            "format=format_name", "-of", "csv=p=0", str(edited),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "mp4" in probe.stdout


def test_post_process_reports_cancellation(tmp_path) -> None:
    ffmpeg = FFmpegManager()
    if not ffmpeg.available:
        pytest.skip("FFmpeg não configurado nesta máquina")
    source = tmp_path / "longo.mp4"
    _run(ffmpeg, [
        str(ffmpeg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=600:size=1280x720:rate=30",
        "-c:v", "libx264", "-preset", "ultrafast", str(source),
    ])
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(RuntimeError, match="cancelado"):
        ffmpeg.post_process(source, editor_compatible=True, cancel=cancel)

    assert source.exists()


def test_post_process_without_ffmpeg_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("mediadownloader.core.ffmpeg_manager.shutil.which", lambda name: None)
    ffmpeg = FFmpegManager(tmp_path)

    with pytest.raises(RuntimeError, match="não está disponível"):
        ffmpeg.post_process(tmp_path / "video.mp4")
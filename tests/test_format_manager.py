from mediadownloader.core.format_manager import FormatManager
from mediadownloader.models import DownloadOptions, MediaType


def test_video_selector_respects_height():
    options = DownloadOptions(video_quality="1080", video_format="mp4")
    selector = FormatManager.selector(options)
    assert "height<=1080" in selector
    assert "ext=mp4" in selector


def test_audio_postprocessor():
    options = DownloadOptions(media_type=MediaType.AUDIO, audio_format="mp3", audio_quality="320")
    processor = FormatManager.postprocessors(options)[0]
    assert processor["key"] == "FFmpegExtractAudio"
    assert processor["preferredquality"] == "320"


def test_audio_adjustment_args_defaults_to_none():
    options = DownloadOptions(media_type=MediaType.AUDIO)
    assert FormatManager.audio_postprocessor_args(options) is None


def test_audio_adjustment_args_speed_only():
    options = DownloadOptions(media_type=MediaType.AUDIO, audio_speed=1.5)
    args = FormatManager.audio_postprocessor_args(options)
    assert args["ExtractAudio+ffmpeg"] == ["-af", "atempo=1.5"]


def test_audio_adjustment_args_pitch_and_speed():
    options = DownloadOptions(media_type=MediaType.AUDIO, audio_speed=1.5, audio_pitch=2 ** (1 / 12))
    args = FormatManager.audio_postprocessor_args(options)
    assert args["ExtractAudio+ffmpeg"] == [
        "-af",
        "aresample=44100,asetrate=46722.3,aresample=44100,atempo=0.943874,atempo=1.5",
    ]


def test_audio_adjustment_args_volume():
    options = DownloadOptions(media_type=MediaType.AUDIO, audio_volume=0.5)
    args = FormatManager.audio_postprocessor_args(options)
    assert args["ExtractAudio+ffmpeg"] == ["-af", "volume=0.5"]


def test_audio_adjustment_ignored_for_video():
    options = DownloadOptions(media_type=MediaType.VIDEO, audio_speed=1.5)
    assert FormatManager.audio_postprocessor_args(options) is None


def test_build_audio_filters_defaults_to_none():
    assert FormatManager.build_audio_filters(1.0, 1.0, 1.0) is None


def test_build_audio_filters_pitch_only():
    chain = FormatManager.build_audio_filters(1.0, 2 ** (1 / 12), 1.0)
    assert chain == (
        "aresample=44100,asetrate=46722.3,aresample=44100,atempo=0.943874"
    )


def test_build_audio_filters_speed_and_volume():
    chain = FormatManager.build_audio_filters(2.0, 1.0, 0.5)
    assert chain == "atempo=2,volume=0.5"


def test_build_audio_filters_all_stages():
    chain = FormatManager.build_audio_filters(1.5, 2 ** (1 / 12), 1.25)
    assert chain == (
        "aresample=44100,asetrate=46722.3,aresample=44100,atempo=0.943874,"
        "atempo=1.5,volume=1.25"
    )


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


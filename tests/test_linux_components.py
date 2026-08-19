from mediadownloader.core.ffmpeg_manager import FFmpegManager


def test_ffmpeg_manager_accepts_bundled_linux_executable_names(tmp_path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    ffmpeg.touch()
    ffprobe.touch()

    manager = FFmpegManager(tmp_path)

    assert manager.ffmpeg == ffmpeg
    assert manager.ffprobe == ffprobe
    assert manager.available is True

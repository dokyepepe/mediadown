"""Offline end-to-end smoke test for analysis, download hooks and FFmpeg audio extraction."""

from __future__ import annotations

import functools
import os
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mediadownloader.core import DownloadEngine, FFmpegManager
from mediadownloader.models import DownloadItem, DownloadOptions, MediaType


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> int:
    ffmpeg = FFmpegManager()
    if not ffmpeg.ffmpeg:
        raise RuntimeError("FFmpeg interno não encontrado.")
    with tempfile.TemporaryDirectory(prefix="media-downloader-smoke-") as temporary:
        root = Path(temporary)
        source = root / "source"
        output = root / "output"
        source.mkdir()
        output.mkdir()
        sample = source / "sample.mp4"
        subprocess.run(
            [
                str(ffmpeg.ffmpeg), "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24",
                "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100", "-t", "2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(sample),
                "-loglevel", "error",
            ],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        handler = functools.partial(QuietHandler, directory=str(source))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/sample.mp4"
            engine = DownloadEngine(ffmpeg)
            media = engine.analyze(url)
            item = DownloadItem(
                url=url, title=media.title, output_path=str(output), media_type=MediaType.AUDIO,
                format="mp3", quality="128 kbps",
            )
            options = DownloadOptions(
                media_type=MediaType.AUDIO, audio_format="mp3", audio_quality="128",
                embed_thumbnail=False, add_metadata=False, output_dir=str(output),
                duplicate_policy="rename",
            )
            events: list[dict] = []
            final_file = engine.download(item, options, events.append, threading.Event())
            final = Path(final_file)
            assert final.exists() and final.suffix == ".mp3" and final.stat().st_size > 0
            assert events and max(event.get("progress", 0) for event in events) == 99.0
            print(
                f"SMOKE_OK title={media.title!r} formats={len(media.formats)} "
                f"output={final.name!r} bytes={final.stat().st_size} events={len(events)}"
            )
        finally:
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


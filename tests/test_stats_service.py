from __future__ import annotations

from pathlib import Path

from mediadownloader.services.stats_service import (
    CleanupResult, StorageStats, collect, is_temporary_file, remove_temporaries,
)


def test_temporary_detection_spares_real_media_files():
    assert is_temporary_file(Path("video.mp4.part"))
    assert is_temporary_file(Path("audio.m4a.ytdl"))
    assert is_temporary_file(Path("movie.mp4.f137028"))
    assert not is_temporary_file(Path("logo.finance.png"))
    assert not is_temporary_file(Path("aula.final.mp4"))
    assert not is_temporary_file(Path("part.mp4"))


def test_collect_reports_totals_and_free_space(tmp_path: Path):
    (tmp_path / "concluido.mp4").write_bytes(b"x" * 100)
    (tmp_path / "perdido.mp4.part").write_bytes(b"y" * 40)

    snapshot = collect([tmp_path], database=tmp_path / "hist.sqlite3")

    assert isinstance(snapshot, StorageStats)
    assert snapshot.completed_count == 0
    assert snapshot.temporary_files == 1
    assert snapshot.temporary_bytes == 40
    assert snapshot.free_bytes is not None and snapshot.free_bytes > 0


def test_collect_creates_missing_directories(tmp_path: Path):
    target = tmp_path / "novo"
    snapshot = collect([target], database=tmp_path / "hist.sqlite3")
    assert target.is_dir()
    assert snapshot.free_bytes is not None


def test_collect_survives_a_directory_it_cannot_create(tmp_path: Path):
    blocker = tmp_path / "arquivo.txt"
    blocker.write_text("sou um arquivo, não uma pasta")

    snapshot = collect([blocker / "subpasta"], database=tmp_path / "hist.sqlite3")

    assert snapshot.free_bytes is None
    assert snapshot.temporary_files == 0


def test_remove_temporaries_only_deletes_abandoned_files(tmp_path: Path):
    keep = tmp_path / "musica.mp3"
    keep.write_bytes(b"keep")
    (tmp_path / "musica.mp3.part").write_bytes(b"junk")
    (tmp_path / "musica.mp3.f123").write_bytes(b"chunk")

    result = remove_temporaries([tmp_path])

    assert isinstance(result, CleanupResult)
    assert result.removed_files == 2
    assert result.freed_bytes == len(b"junk") + len(b"chunk")
    assert result.errors == 0
    assert keep.exists()
    assert not (tmp_path / "musica.mp3.part").exists()


def test_remove_temporaries_counts_directories_as_duplicates_only_once(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "x.mp4.part").write_bytes(b"1")
    (tmp_path / "b" / "y.mp4.part").write_bytes(b"2")

    result = remove_temporaries([tmp_path / "a", tmp_path / "b", tmp_path / "a"])

    assert result.removed_files == 2

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mediadownloader.core.download_gate import (
    GateConfig, clamp_minute, evaluate, format_minute, free_space_bytes, minute_of_day,
    window_allows,
)


def test_clamp_and_format_cover_the_whole_day():
    assert clamp_minute(-30) == 0
    assert clamp_minute("90") == 90
    assert clamp_minute(None) == 0
    assert clamp_minute(9_999) == 1_439
    assert format_minute(0) == "00:00"
    assert format_minute(360) == "06:00"
    assert format_minute(1_439) == "23:59"


def test_window_allows_handles_same_day_and_wrapping_ranges():
    at = datetime(2026, 3, 1, 12, 0)
    assert window_allows(0, 1_439, at)
    assert window_allows(0, 60, at) is False
    assert window_allows(540, 1_440, at) is True
    # 23:00 -> 06:00 wraps past midnight.
    assert window_allows(1_380, 360, datetime(2026, 3, 1, 23, 30)) is True
    assert window_allows(1_380, 360, datetime(2026, 3, 1, 2, 0)) is True
    assert window_allows(1_380, 360, datetime(2026, 3, 1, 12, 0)) is False
    # Equal endpoints mean "always allowed", never a dead queue.
    assert window_allows(360, 360, datetime(2026, 3, 1, 12, 0)) is True


def test_minute_of_day_matches_the_window():
    assert minute_of_day(datetime(2026, 3, 1, 6, 5)) == 365


def test_free_space_is_none_for_unusable_directories(tmp_path: Path):
    assert free_space_bytes(tmp_path) is not None
    missing = tmp_path / "ausente" / "pasta"
    assert free_space_bytes(missing) is None


def test_evaluate_blocks_outside_the_window_without_free_space_pressure(tmp_path: Path):
    decision = evaluate(
        GateConfig(window_enabled=True, window_start_minute=540, window_end_minute=1_080),
        moment=datetime(2026, 3, 1, 20, 0),
        download_dirs=[str(tmp_path)],
    )
    assert decision.allowed is False
    assert "09:00" in decision.reason and "18:00" in decision.reason


def test_evaluate_allows_inside_the_window_with_room_on_disk(tmp_path: Path):
    decision = evaluate(
        GateConfig(window_enabled=True, window_start_minute=360, window_end_minute=540),
        moment=datetime(2026, 3, 1, 6, 30),
        download_dirs=[str(tmp_path)],
    )
    assert decision.allowed is True
    assert bool(decision) is True
    assert decision.reason == ""


def test_evaluate_stops_when_the_disk_is_almost_full(tmp_path: Path):
    decision = evaluate(
        GateConfig(window_enabled=False, minimum_free_bytes=1024 ** 4),
        moment=datetime(2026, 3, 1, 12, 0),
        download_dirs=[str(tmp_path)],
    )
    assert decision.allowed is False
    assert "Espaço livre" in decision.reason


def test_evaluate_honours_an_explicit_free_space_reading(tmp_path: Path):
    decision = evaluate(
        GateConfig(minimum_free_bytes=1_000),
        moment=datetime(2026, 3, 1, 12, 0),
        free_bytes=999,
    )
    assert decision.allowed is False


def test_evaluate_skips_the_disk_probe_without_a_threshold(tmp_path: Path):
    decision = evaluate(
        GateConfig(window_enabled=False, minimum_free_bytes=0),
        moment=datetime(2026, 3, 1, 12, 0),
        download_dirs=[str(tmp_path / "inexistente" / "profundo")],
    )
    assert decision.allowed is True


def test_evaluate_keeps_going_when_free_space_is_unknown(tmp_path: Path):
    decision = evaluate(
        GateConfig(minimum_free_bytes=1024 ** 4),
        moment=datetime(2026, 3, 1, 12, 0),
        download_dirs=[str(tmp_path / "inexistente" / "profundo")],
    )
    assert decision.allowed is True


def test_gate_config_from_settings_uses_documented_defaults():
    class FakeSettings:
        @staticmethod
        def get(key, default=None):
            values = {
                "downloads.window_enabled": True,
                "downloads.window_start_minute": 9_999,
                "downloads.window_end_minute": -5,
                "downloads.minimum_free_mb": 64,
            }
            return values.get(key, default)

    config = GateConfig.from_settings(FakeSettings())
    assert config.window_enabled is True
    assert config.window_start_minute == 1_439
    assert config.window_end_minute == 0
    assert config.minimum_free_bytes == 64 * 1024 * 1024

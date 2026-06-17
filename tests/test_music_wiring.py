"""Unit test wiring nhạc cảm xúc — cờ CLI/wrapper phải map vào PipelineConfig.

Bắt bug: SKILL hướng dẫn dùng --music-library/--music-mode nhưng cờ chưa tồn tại
hoặc không map → emotion music không reachable end-to-end. KHÔNG cần ffmpeg.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _PLUGIN_ROOT / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))


def test_cli_maps_emotion_flags():
    from videopipe import cli

    parser = cli.build_parser()
    args = parser.parse_args(
        ["topic x", "--music-mode", "emotion", "--music-library", str(_PLUGIN_ROOT / "assets" / "music")]
    )
    config = cli._build_config_from_args(args)

    assert config.music_mode == "emotion"
    assert config.music_library == _PLUGIN_ROOT / "assets" / "music"


def test_cli_music_mode_default_static():
    from videopipe import cli

    args = cli.build_parser().parse_args(["topic x"])
    config = cli._build_config_from_args(args)

    assert config.music_mode == "static"
    assert config.music_library is None

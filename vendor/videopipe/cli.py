"""Entrypoint dòng lệnh: python -m videopipe "<topic>".

Parse tham số → dựng PipelineConfig → in config đã resolve → chạy pipeline.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from videopipe.config import STYLE_PRESETS, PipelineConfig, get_style_preset
from videopipe.pipeline import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videopipe",
        description="Tạo video kể chuyện từ một chủ đề (MVP: ảnh tĩnh + TTS + sub).",
    )
    parser.add_argument(
        "topic",
        help="Chủ đề câu chuyện (tiếng Anh). Nếu --from-trending: đây là seed query.",
    )
    parser.add_argument(
        "--from-trending",
        action="store_true",
        help="Dùng last30days tìm chủ đề trending từ seed (thay vì dùng topic trực tiếp).",
    )
    parser.add_argument(
        "--storyboard",
        default=None,
        help="Đường dẫn file storyboard JSON (Claude tự viết) → dựng video dài, resume-friendly.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Chỉ định run_id để RESUME một run dở (dùng cùng --storyboard).",
    )
    parser.add_argument(
        "--voice", default=None, help="Override giọng edge-tts (vd: en-US-GuyNeural)."
    )
    parser.add_argument("--fps", type=int, default=None, help="Override khung hình/giây.")
    parser.add_argument(
        "--scenes", type=int, default=4, help="Số scene trong kịch bản (mặc định 4)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ resolve + in config, không chạy pipeline.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log chi tiết (DEBUG)."
    )
    # --- Preset phong cách hình ảnh ---
    parser.add_argument(
        "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="cinematic",
        help=(
            "Chọn preset phong cách hình ảnh. "
            f"Hợp lệ: {', '.join(sorted(STYLE_PRESETS.keys()))}. "
            "Mặc định: cinematic."
        ),
    )
    # --- Nhạc nền ---
    parser.add_argument(
        "--music",
        type=_existing_path,
        default=None,
        metavar="PATH",
        help="Đường dẫn file nhạc nền mp3 (phải tồn tại).",
    )
    parser.add_argument(
        "--music-duck-db",
        type=float,
        default=None,
        metavar="DB",
        help="Mức giảm âm nhạc so với giọng (dB). Mặc định 16.0.",
    )
    # --- Ngân sách thời lượng ---
    parser.add_argument(
        "--target-minutes",
        type=float,
        default=None,
        metavar="N",
        help="Thời lượng mục tiêu (phút). Pipeline cảnh báo nếu thực tế lệch >10%%.",
    )
    return parser


def _existing_path(value: str) -> Path:
    """argparse type: chuyển chuỗi → Path, báo lỗi nếu file không tồn tại."""
    p = Path(value)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"File không tồn tại: {value}")
    return p


def _build_config_from_args(args: argparse.Namespace) -> PipelineConfig:
    """Dựng PipelineConfig từ Namespace đã parse.

    Tách thành hàm riêng để unit test không cần chạy main() đầy đủ.
    """
    overrides: dict = {}
    if args.voice:
        overrides["voice"] = args.voice
    if args.fps:
        overrides["fps"] = args.fps
    if getattr(args, "run_id", None):
        overrides["run_id"] = args.run_id

    # Style preset: ánh xạ tên CLI → StylePreset.
    overrides["style"] = get_style_preset(args.style)

    # Nhạc nền.
    if args.music is not None:
        overrides["music_path"] = args.music
    if args.music_duck_db is not None:
        overrides["music_duck_db"] = args.music_duck_db

    # Ngân sách thời lượng.
    if getattr(args, "target_minutes", None) is not None:
        overrides["target_minutes"] = args.target_minutes

    return PipelineConfig(topic=args.topic, **overrides)


def _force_utf8_stdio() -> None:
    """Ép stdout/stderr sang UTF-8 để log tiếng Việt không vỡ trên console Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = _build_config_from_args(args)
    print(config.describe())

    if args.dry_run:
        config.ensure_dirs()
        print(f"\n[dry-run] Đã tạo {config.work_dir}; bỏ qua pipeline.")
        return 0

    # Video dài từ storyboard (Claude tự viết) — resume-friendly.
    if args.storyboard:
        from videopipe.pipeline import run_storyboard
        from videopipe.storyboard import Storyboard

        board = Storyboard.load(Path(args.storyboard))
        run_storyboard(config, board)
        return 0

    run(config, n_scenes=args.scenes, from_trending=args.from_trending)
    return 0


if __name__ == "__main__":
    sys.exit(main())

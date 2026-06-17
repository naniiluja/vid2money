"""Wrapper script — cầu nối từ môi trường plugin → vendor videopipe pipeline.

Vai trò: set env đúng (VIDEOPIPE_WORK_ROOT, VIDEOPIPE_ASSETS_ROOT) TRƯỚC KHI
import videopipe, để artifact rơi vào <cwd>/video-out/ (thư mục project người
dùng) thay vì thư mục plugin. Sau đó load storyboard và gọi run_storyboard().

Thứ tự bắt buộc:
  1. set os.environ  ← MỌI ENV PHẢI SET TRƯỚC BƯỚC NÀY
  2. sys.path.insert (vendor)
  3. from videopipe import ...   ← import XẢY RA SAU KHI env đã set

Nếu đảo thứ tự, config._work_root() / _assets_root() đọc env lúc truy cập
(không lúc import) nên vẫn hoạt động — nhưng vendor path thêm vào sys.path
phải sau set-env để tránh lỗi import không tìm thấy module.

Chạy: python run_pipeline.py --storyboard <file.json> [options]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Hằng số đường dẫn (tính từ vị trí file này)
# ---------------------------------------------------------------------------

# Script nằm ở skills/video-storyteller/scripts/ — gốc plugin = parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT_FROM_FILE = _SCRIPT_DIR.parent.parent.parent  # parents[3] = plugin root


def _resolve_plugin_root() -> Path:
    """Trả thư mục gốc plugin.

    Ưu tiên env CLAUDE_PLUGIN_ROOT (set bởi harness plugin khi chạy trong plugin
    context). Nếu không có (chạy trực tiếp / dev / test), suy từ __file__.
    """
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if raw:
        return Path(raw)
    return _PLUGIN_ROOT_FROM_FILE


def _resolve_paths(cwd: Path | None = None) -> tuple[Path, Path, Path]:
    """Tính toán các đường dẫn cần thiết, set env, trả (plugin_root, vendor, work_root).

    Hàm này được tách riêng để có thể unit test mà không cần import videopipe.

    Thứ tự trong hàm:
      1. Tính plugin_root + work_root + assets_root.
      2. Set os.environ (VIDEOPIPE_WORK_ROOT + VIDEOPIPE_ASSETS_ROOT).
      Caller chịu trách nhiệm sys.path + import videopipe SAU khi gọi hàm này.

    Args:
        cwd: thư mục làm việc (mặc định Path.cwd()). Inject qua test.

    Returns:
        (plugin_root, vendor_dir, work_root_path)
    """
    if cwd is None:
        cwd = Path.cwd()

    plugin_root = _resolve_plugin_root()
    vendor_dir = plugin_root / "vendor"

    # Artifact rơi vào <cwd>/video-out/ (thư mục project người dùng, không phải plugin).
    work_root = cwd / "video-out"
    assets_root = plugin_root / "assets"

    # Set env TRƯỚC khi import videopipe (import-timing seam — xem docstring module).
    os.environ["VIDEOPIPE_WORK_ROOT"] = str(work_root)
    os.environ["VIDEOPIPE_ASSETS_ROOT"] = str(assets_root)

    return plugin_root, vendor_dir, work_root


def _build_config(args: argparse.Namespace, board_title: str):
    """Dựng PipelineConfig từ args đã parse.

    Import videopipe được thực hiện lazy bên trong để hàm chỉ chạy SAU khi
    sys.path đã bao gồm vendor. Trả PipelineConfig.
    """
    # Import lazy — PHẢI sau _resolve_paths() đã set env + sys.path đã inject vendor.
    from videopipe.config import PipelineConfig, get_style_preset  # noqa: PLC0415

    style = get_style_preset(args.style)

    music_path: Path | None = None
    if args.music:
        music_path = Path(args.music)

    config_kwargs: dict = dict(
        topic=board_title,
        image_backend=args.backend,
        style=style,
        music_path=music_path,
    )
    if args.run_id:
        config_kwargs["run_id"] = args.run_id
    if args.music_duck_db is not None:
        config_kwargs["music_duck_db"] = args.music_duck_db
    if args.outro_text:
        config_kwargs["outro_text"] = args.outro_text

    return PipelineConfig(**config_kwargs)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Tách hàm để test không cần subprocess."""
    parser = argparse.ArgumentParser(
        description="Wrapper pipeline video — set path env rồi gọi videopipe."
    )
    parser.add_argument(
        "--storyboard", required=True, help="Đường dẫn tới file storyboard JSON."
    )
    parser.add_argument(
        "--run-id", default="", help="Run ID để resume (tùy chọn)."
    )
    parser.add_argument(
        "--style", default="stick-figure",
        help="Tên style preset: cinematic | stick-figure (mặc định: stick-figure)."
    )
    parser.add_argument(
        "--music", default="", help="Đường dẫn file nhạc nền mp3 (tùy chọn)."
    )
    parser.add_argument(
        "--music-duck-db", type=float, default=None,
        help="Mức giảm âm nhạc nền so với giọng đọc (dB, mặc định 16.0)."
    )
    parser.add_argument(
        "--backend", choices=["codex"], default="codex",
        help="Backend sinh ảnh: codex (mặc định, duy nhất ở lớp plugin)."
    )
    parser.add_argument(
        "--outro-text", default="", help="Chữ hiển thị trên end card (tùy chọn)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point chính — dùng được cả khi gọi trực tiếp lẫn từ test.

    Thứ tự bắt buộc (không được đảo):
      1. Parse args.
      2. _resolve_paths() → set env VIDEOPIPE_WORK_ROOT + VIDEOPIPE_ASSETS_ROOT.
      3. sys.path.insert vendor.
      4. Import videopipe (lazy, trong _build_config + run_storyboard).
      5. Gọi pipeline.
    """
    # Đảm bảo stdout UTF-8 trên Windows (tránh cp1252 vỡ tiếng Việt / đường dẫn).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger("videopipe.runner")

    # [1] Parse args.
    args = _parse_args(argv)

    # [2] Resolve paths + set env TRƯỚC khi import videopipe.
    plugin_root, vendor_dir, work_root = _resolve_paths()
    log.info("Plugin root   : %s", plugin_root)
    log.info("Vendor dir    : %s", vendor_dir)
    log.info("Work root     : %s", work_root)

    # [3] Thêm vendor vào sys.path (idempotent — check trước khi insert).
    vendor_str = str(vendor_dir)
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)

    # [4+5] Import videopipe (lazy) + chạy pipeline.
    from videopipe.pipeline import run_storyboard  # noqa: PLC0415
    from videopipe.storyboard import Storyboard  # noqa: PLC0415

    storyboard_path = Path(args.storyboard)
    if not storyboard_path.exists():
        raise ValueError(f"Storyboard không tồn tại: {storyboard_path}")

    board = Storyboard.load(storyboard_path)
    log.info("Storyboard: %s — %d shot", board.title, len(board.shots))

    config = _build_config(args, board.title)
    log.info("Config dựng xong: run_id=%s, backend=%s", config.run_id, config.image_backend)

    final_path = run_storyboard(config, board)

    # In final path ra stdout để caller (SKILL.md / script khác) lấy kết quả.
    print(str(final_path))


if __name__ == "__main__":
    main()

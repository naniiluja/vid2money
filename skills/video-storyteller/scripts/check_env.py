"""Script probe môi trường — kiểm tra các công cụ cần thiết để chạy pipeline.

Chạy: python check_env.py --json
Output: JSON ra stdout với các field:
  - tools: dict {tên: bool} (có/không)
  - recommended_backend: "codex" (backend ảnh duy nhất của plugin)
  - blockers: list lý do pipeline chưa chạy được
  - warnings: list cảnh báo cần chú ý nhưng không block
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

# Thư mục gốc plugin = cha của skills/ (3 cấp lên từ script này)
# skills/video-storyteller/scripts/check_env.py → plugin root
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _check_vendored_stdin_fix() -> bool:
    """Kiểm tra vendor/videopipe/images.py có dùng STDIN invocation cho codex không.

    Tìm dấu hiệu: subprocess.run được gọi với `input=` (truyền prompt qua stdin)
    trong nhánh codex. Đây là fix chống context-bleed trên Windows (2026-06-16).
    Trả True nếu tìm thấy bằng chứng STDIN, False nếu không.
    """
    images_path = _PLUGIN_ROOT / "vendor" / "videopipe" / "images.py"
    if not images_path.exists():
        return False
    try:
        content = images_path.read_text(encoding="utf-8", errors="replace")
        # Dấu hiệu 1: subprocess.run với input= (truyền stdin data)
        has_input_kwarg = "input=stdin_data" in content or ("input=" in content and "subprocess.run" in content)
        # Dấu hiệu 2: dùng "-" làm positional arg (stdin placeholder của codex)
        has_stdin_dash = '"-"' in content or "'-'" in content
        return has_input_kwarg and has_stdin_dash
    except OSError:
        return False


def probe_environment() -> dict:
    """Kiểm tra toàn bộ môi trường và trả dict kết quả.

    Hàm thuần (không side-effect ngoài filesystem read) — dễ test với mock.
    Backend ảnh duy nhất của plugin là Codex — không còn anti2api/Gemini.
    """
    # --- Probe từng công cụ ---
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    codex_path = shutil.which("codex")
    edge_tts_spec = importlib.util.find_spec("edge_tts")

    tools: dict[str, bool] = {
        "ffmpeg": ffmpeg_path is not None,
        "ffprobe": ffprobe_path is not None,
        "codex": codex_path is not None,
        "edge-tts": edge_tts_spec is not None,
    }

    # --- Backend duy nhất là codex ---
    recommended_backend = "codex"

    # --- Tính blockers (điều kiện bắt buộc để pipeline chạy) ---
    blockers: list[str] = []
    if not tools["ffmpeg"]:
        blockers.append(
            "ffmpeg không tìm thấy trong PATH — cài ffmpeg (https://ffmpeg.org/download.html) "
            "rồi thêm vào PATH."
        )
    if not tools["ffprobe"]:
        blockers.append(
            "ffprobe không tìm thấy trong PATH — ffprobe thường đi kèm ffmpeg; "
            "kiểm tra lại cài đặt."
        )
    if not tools["edge-tts"]:
        blockers.append(
            "edge-tts chưa cài — chạy: pip install edge-tts>=6.1.0"
        )

    # --- Tính warnings ---
    warnings: list[str] = []

    # CODEX FALLBACK GUARD (premortem H): cảnh báo rủi ro context-bleed trên Windows.
    if platform.system() == "Windows":
        warnings.append(
            "CẢNH BÁO CODEX/WINDOWS: codex.CMD trên Windows từng cắt xén prompt "
            "positional arg dài → mất style anchor → context-bleed (ảnh ra sai style "
            "photorealistic thay vì người que). Bản vendored đã fix bằng STDIN ('-' "
            "positional + input= stdin) — an toàn để dùng. Nếu vẫn gặp ảnh sai style: "
            "xóa ảnh đó rồi chạy lại pipeline với cùng run-id để gen lại."
        )
        # Kiểm tra vendor images.py thực sự có fix STDIN chưa.
        if not _check_vendored_stdin_fix():
            warnings.append(
                "QUAN TRỌNG: vendor/videopipe/images.py có thể thiếu fix context-bleed STDIN "
                "— không tìm thấy dấu hiệu 'input=stdin_data' + '-' positional trong nhánh codex. "
                "Re-vendor từ D:/projects/youtube/videopipe/images.py (bản sau 2026-06-16)."
            )

    return {
        "tools": tools,
        "recommended_backend": recommended_backend,
        "blockers": blockers,
        "warnings": warnings,
    }


def _human_report(result: dict) -> str:
    """Tạo báo cáo dễ đọc từ dict kết quả probe."""
    lines: list[str] = ["=== Video Storyteller — Kiểm tra môi trường ===", ""]
    lines.append("Công cụ:")
    for tool, ok in result["tools"].items():
        mark = "OK" if ok else "THIẾU"
        lines.append(f"  [{mark}] {tool}")
    lines.append("")
    lines.append(f"Backend khuyên dùng: {result['recommended_backend']}")
    lines.append("")
    if result["blockers"]:
        lines.append("BLOCKER (pipeline chưa chạy được):")
        for b in result["blockers"]:
            lines.append(f"  - {b}")
    else:
        lines.append("Pipeline sẵn sàng chạy (không có blocker).")
    lines.append("")
    if result["warnings"]:
        lines.append("Cảnh báo:")
        for w in result["warnings"]:
            lines.append(f"  ! {w}")
    return "\n".join(lines)


def main() -> None:
    """Entry point: parse --json flag, chạy probe, in kết quả ra stdout."""
    parser = argparse.ArgumentParser(
        description="Probe môi trường để chạy video-storyteller pipeline."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="In JSON ra stdout (mặc định bật).",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="In báo cáo dễ đọc thay vì JSON.",
    )
    args = parser.parse_args()

    result = probe_environment()

    # Đảm bảo stdout UTF-8 trên Windows (tránh cp1252 vỡ tiếng Việt).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    if args.human:
        print(_human_report(result))
    else:
        # Mặc định in JSON (--json là default True, --human ghi đè).
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

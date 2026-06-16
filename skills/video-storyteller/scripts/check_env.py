"""Script probe môi trường — kiểm tra các công cụ cần thiết để chạy pipeline.

Chạy: python check_env.py --json
Output: JSON ra stdout với các field:
  - tools: dict {tên: bool} (có/không)
  - recommended_backend: "gemini" hoặc "codex"
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
import urllib.request
import urllib.error
from pathlib import Path

# Thư mục gốc plugin = cha của skills/ (3 cấp lên từ script này)
# skills/video-storyteller/scripts/check_env.py → plugin root
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _probe_anti2api(base_url: str, timeout_s: float = 2.5) -> bool:
    """Thử kết nối tới anti2api server, trả True nếu server PHẢN HỒI (sống).

    Dùng urllib thuần — không thêm dependency ngoài. KHÔNG in/log API key.

    ROOT CAUSE (fix 2026-06-16): probe root URL trả HTTP 404 vì server KHÔNG có
    route ở "/" — nhưng 404 NGHĨA LÀ SERVER SỐNG (chỉ thiếu route đó). Phải bắt
    HTTPError RIÊNG (4xx/5xx = server đang phản hồi = sống), chỉ URLError
    (connection refused / DNS / timeout) mới là server CHẾT. Probe endpoint
    `/v1/models` cho khớp ngữ cảnh OpenAI-compat (server đòi key → 401, vẫn là sống).
    """
    url = base_url.rstrip("/") + "/v1/models"
    try:
        urllib.request.urlopen(url, timeout=timeout_s)
        return True
    except urllib.error.HTTPError:
        # Server trả mã lỗi HTTP (401 Invalid Key, 404...) → server SỐNG.
        return True
    except Exception:
        # URLError (connection refused, timeout, DNS) → server CHẾT.
        return False


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

    Hàm thuần (không side-effect ngoài network probe) — dễ test với mock.
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

    # --- Probe anti2api ---
    anti2api_base = os.environ.get("ANTI2API_BASE_URL", "http://localhost:8046")
    anti2api_key_set = bool(os.environ.get("ANTI2API_KEY", "").strip())
    anti2api_alive = _probe_anti2api(anti2api_base)
    tools["anti2api"] = anti2api_alive

    # --- Tính recommended_backend ---
    # Dùng gemini nếu server sống VÀ có key; ngược lại dùng codex.
    if anti2api_alive and anti2api_key_set:
        recommended_backend = "gemini"
    else:
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
    if recommended_backend == "codex" and platform.system() == "Windows":
        warnings.append(
            "CẢNH BÁO CODEX/WINDOWS: codex.CMD trên Windows từng cắt xén prompt "
            "positional arg dài → mất style anchor → context-bleed (ảnh ra sai style "
            "photorealistic thay vì người que). Bản vendored đã fix bằng STDIN ('-' "
            "positional + input= stdin). KHUYẾN NGHỊ: bật anti2api/Gemini backend để "
            "portable và chất lượng ảnh tốt hơn (set ANTI2API_BASE_URL + ANTI2API_KEY)."
        )
        # Kiểm tra vendor images.py thực sự có fix STDIN chưa.
        if not _check_vendored_stdin_fix():
            warnings.append(
                "QUAN TRỌNG: vendor/videopipe/images.py có thể thiếu fix context-bleed STDIN "
                "— không tìm thấy dấu hiệu 'input=stdin_data' + '-' positional trong nhánh codex. "
                "Re-vendor từ D:/projects/youtube/videopipe/images.py (bản sau 2026-06-16)."
            )

    # Thêm info anti2api nếu server chết hoặc thiếu key (nhưng không phải blocker).
    if not anti2api_alive:
        warnings.append(
            f"anti2api server không phản hồi tại {anti2api_base} — "
            "nếu muốn dùng backend Gemini, chạy: cd D:\\projects\\anti2api && npm start"
        )
    elif not anti2api_key_set:
        warnings.append(
            "ANTI2API_KEY chưa được set trong env — server sống nhưng request sẽ bị từ chối. "
            "Chạy: export ANTI2API_KEY=<key> (lấy từ D:\\projects\\anti2api\\.env)."
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

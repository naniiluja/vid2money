"""Bước [1] research — tìm chủ đề trending qua skill last30days.

Gọi engine last30days.py (positional topic + --emit json) trên các nguồn keyless
(reddit/youtube/hackernews/polymarket/github), lấy cluster nổi bật nhất làm topic
+ evidence để feed sang script_gen.

Lưu ý (đã verify 2026-06-16): chỉ các nguồn trên là keyless; --web-backend none
để không cần API key. Nếu research thất bại, pipeline vẫn chạy được qua --topic.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("videopipe")


def _resolve_last30days() -> Path:
    """Tìm script last30days.py theo thứ tự ưu tiên: env → cache → lỗi rõ.

    Ưu tiên:
    1. Biến môi trường LAST30DAYS_PATH (nếu trỏ file tồn tại).
    2. Tự dò trong ~/.claude/plugins/cache/last30days*/ (glob đệ quy tìm last30days.py).
    3. Không thấy → RuntimeError hướng dẫn cách set.
    """
    # 1. Kiểm tra biến môi trường trước.
    env_val = os.environ.get("LAST30DAYS_PATH", "")
    if env_val:
        env_path = Path(env_val)
        if env_path.is_file():
            log.debug("last30days resolve từ env LAST30DAYS_PATH: %s", env_path)
            return env_path
        log.warning("LAST30DAYS_PATH=%s không tồn tại — thử tự dò trong cache.", env_val)

    # 2. Tự dò trong plugin cache (~/.claude/plugins/cache/last30days*/).
    cache_base = Path.home() / ".claude" / "plugins" / "cache"
    # Glob tất cả thư mục bắt đầu bằng "last30days", tìm last30days.py đệ quy.
    candidates: list[Path] = sorted(
        cache_base.glob("last30days*/last30days.py")
    ) + sorted(
        cache_base.glob("last30days*/**/last30days.py")
    )
    # Khử trùng lặp, giữ thứ tự (sorted → phiên bản cao nhất thường ở cuối).
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if unique:
        chosen = unique[-1]  # Lấy phiên bản mới nhất (sort chữ cái → cao hơn)
        log.debug("last30days resolve từ cache: %s", chosen)
        return chosen

    # 3. Không tìm thấy → RuntimeError rõ ràng.
    raise RuntimeError(
        "Không tìm thấy script last30days.py.\n"
        "Cách fix:\n"
        "  • Cài skill: mở Claude Code → /last30days (chạy một lần để cache).\n"
        "  • Hoặc set env: LAST30DAYS_PATH=/đường/dẫn/tới/last30days.py\n"
        f"  • Cache tìm trong: {cache_base / 'last30days*'}"
    )


@dataclass
class Topic:
    title: str
    summary: str
    evidence: str  # text gọn để nhồi vào prompt viết kịch bản


def _flatten_text(obj, limit: int = 1200) -> str:
    """Gom các chuỗi 'title'/'summary'/'text' từ JSON lồng nhau thành 1 đoạn."""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key in ("title", "summary", "text", "headline"):
                val = node.get(key)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    joined = " · ".join(dict.fromkeys(parts))  # khử trùng lặp, giữ thứ tự
    return joined[:limit]


def find_trending(
    seed_query: str, save_dir: Path, quick: bool = True, timeout_s: int = 300
) -> Topic:
    """Chạy last30days cho seed_query, trả về Topic nổi bật để viết kịch bản."""
    # Resolve động — env trước, cache sau, lỗi rõ nếu không thấy.
    l30d = _resolve_last30days()

    save_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python", str(l30d), seed_query,
        "--emit", "json", "--web-backend", "none",
        "--save-dir", str(save_dir),
    ]
    if quick:
        cmd.append("--quick")

    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"last30days exit {proc.returncode}: {proc.stderr[-500:]}")

    # Bóc JSON từ stdout.
    start, end = proc.stdout.find("{"), proc.stdout.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"Không có JSON trong output last30days:\n{proc.stdout[:400]}")
    data = json.loads(proc.stdout[start : end + 1])

    evidence = _flatten_text(data)
    # Title: ưu tiên field title cấp cao, fallback seed_query.
    title = data.get("title") or data.get("topic") or seed_query
    summary = data.get("summary", "")[:300] if isinstance(data.get("summary"), str) else ""
    log.info("Trending: %s (%d ký tự evidence)", title, len(evidence))
    return Topic(title=str(title), summary=summary, evidence=evidence)

"""Structural test cho skill grill-video (SKILL.md là contract Markdown).

Không test hành vi interview (one-question/recommend/summary — không kiểm
được bằng pytest). Chỉ kiểm contract tĩnh của file:
  - File tồn tại.
  - Frontmatter: user-invocable: false + allowed-tools chứa AskUserQuestion/Read/Glob/Grep.
  - Chống drift: mọi --flag nhắc trong body PHẢI tồn tại trong run_pipeline.py _parse_args.
  - KHÔNG nhắc --voice (chưa hỗ trợ ở lớp wrapper).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SKILL = _ROOT / "skills" / "grill-video" / "SKILL.md"
_PARENT_SKILL = _ROOT / "skills" / "video-storyteller" / "SKILL.md"
_RUN_PIPELINE = (
    _ROOT / "skills" / "video-storyteller" / "scripts" / "run_pipeline.py"
)

# Header contract — cả grill-video lẫn skill cha phải dùng đúng chuỗi này
# để skill cha parse được summary trả về (coupling cross-file).
_SUMMARY_HEADER = "## Chi tiết đã thu thập"


def _read_skill() -> str:
    assert _SKILL.exists(), f"Thiếu SKILL.md: {_SKILL}"
    return _SKILL.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> str:
    """Tách khối YAML frontmatter giữa cặp '---' đầu file."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    assert m, "SKILL.md thiếu frontmatter YAML hợp lệ (cặp ---)."
    return m.group(1)


def test_skill_file_exists() -> None:
    _read_skill()


def test_frontmatter_user_invocable_false() -> None:
    fm = _split_frontmatter(_read_skill())
    # user-invocable: false (KHÔNG dùng disable-model-invocation — skill cha cần thấy description).
    assert re.search(r"^\s*user-invocable:\s*false\s*$", fm, re.MULTILINE), \
        "Frontmatter phải có 'user-invocable: false'."


def test_frontmatter_allowed_tools() -> None:
    fm = _split_frontmatter(_read_skill())
    m = re.search(r"^\s*allowed-tools:\s*(.+)$", fm, re.MULTILINE)
    assert m, "Frontmatter phải có 'allowed-tools'."
    tools = m.group(1)
    for required in ("AskUserQuestion", "Read", "Glob", "Grep"):
        assert required in tools, f"allowed-tools thiếu {required!r}."


def _pipeline_flags() -> set[str]:
    """Trích mọi --flag khai báo trong _parse_args của run_pipeline.py."""
    text = _RUN_PIPELINE.read_text(encoding="utf-8")
    return set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', text))


def test_flags_in_body_match_pipeline() -> None:
    """Chống drift: --flag nào nhắc trong SKILL.md cũng phải có thật trong pipeline."""
    body = _read_skill()
    valid = _pipeline_flags()
    # Sentinel: nếu regex trích flag hỏng (re-vendor đổi cách add_argument),
    # bài test này fail to tiếng thay vì pass rỗng.
    assert "--storyboard" in valid, (
        "Trích flag từ run_pipeline.py hỏng — '--storyboard' phải luôn có. Kiểm regex _pipeline_flags."
    )
    used = set(re.findall(r"(--[a-z][a-z0-9-]+)", body))
    unknown = used - valid
    assert not unknown, (
        f"SKILL.md nhắc flag không tồn tại trong run_pipeline._parse_args: {sorted(unknown)}"
    )


def test_no_voice_flag() -> None:
    body = _read_skill()
    assert "--voice" not in body, \
        "grill-video KHÔNG được nhắc --voice (chưa hỗ trợ ở lớp wrapper)."


def test_summary_header_contract() -> None:
    """Cross-file contract: skill cha parse summary qua đúng header này.

    Nếu đổi header ở một file mà quên file kia → skill cha map flag thất bại
    thầm lặng. Test biến drift thầm lặng thành đỏ.
    """
    assert _SUMMARY_HEADER in _read_skill(), \
        f"grill-video/SKILL.md thiếu header summary {_SUMMARY_HEADER!r}."
    assert _PARENT_SKILL.exists(), f"Thiếu skill cha: {_PARENT_SKILL}"
    assert _SUMMARY_HEADER in _PARENT_SKILL.read_text(encoding="utf-8"), \
        f"video-storyteller/SKILL.md (Bước 2) phải tham chiếu header {_SUMMARY_HEADER!r}."

# Coding Conventions

## Formatting (verifiable)
- Indentation: 4-space (chuẩn PEP 8 Python). Markdown command/SKILL: 2-space list.
- Không có formatter/linter tự động cấu hình trong repo (không black/ruff config). Giữ phong cách PEP 8 thủ công, nhất quán với code hiện có.

## Naming
- Files/module: snake_case (`run_pipeline.py`, `ffmpeg_ops.py`).
- Hàm/biến: snake_case. Helper nội bộ: prefix `_` (`_resolve_paths`, `_merge_srt`, `_neutral_cwd`). Hàm public action-verb (`synthesize`, `generate_image`, `make_segment`, `run_storyboard`).
- Class: CapitalCase, ưu tiên `@dataclass` (`PipelineConfig`, `StylePreset` frozen, `Storyboard`, `Shot`).
- Hằng module: UPPER_SNAKE (`STYLE_PRESETS`, `_DEFAULT_*`).

## File structure
- Một file ~≤ 550 dòng; tách nếu vượt (`ffmpeg_ops.py` ~542 là trần thực tế hiện tại).
- Đầu mỗi module: `from __future__ import annotations` → type hints forward-ref an toàn.
- Module docstring tiếng Việt mô tả vai trò + luồng chính (xem `pipeline.py:1`).
- Logger module-level: `log = logging.getLogger("videopipe")`. Xem `logging.md`.

## General rules
- No dead code / unused imports.
- **Đường dẫn: luôn `pathlib.Path`, không string ghép.** Path trong shell/lệnh: bao dấu nháy kép, ưu tiên `/`.
- Comment phải khớp ngôn ngữ codebase (**tiếng Việt**) — docstring + comment hiện có đều tiếng Việt.
- Hàm thuần (pure) tách riêng khỏi hàm side-effect (`_srt_last_end_seconds`, `_apply_srt_offset` là pure).
- Enforceable coding rules sống ở ĐÂY trong `.claude/rules` (subagent tự nạp); KHÔNG chỉ để trong output style.

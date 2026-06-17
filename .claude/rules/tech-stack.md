# Tech Stack

Philosophy: prefer the **most stable, most widely-supported, least-buggy** stack — mainstream, avoid bleeding-edge. For each library, pick the most popular / best-maintained option.

## Chosen stack
- Ngôn ngữ: **Python 3.11+** (engine), Markdown (command + SKILL contract Claude Code).
- Đóng gói: **Claude Code plugin** (`.claude-plugin/plugin.json` + `marketplace.json`) — không build truyền thống.
- Engine: `vendor/videopipe/` — package Python thuần, version khớp `plugin.json` (hiện `0.1.0`).
- Không có DB, không web framework, không frontend. "Lưu trữ" = filesystem artifact dưới `work/<run-id>/`. Xem `data-layer` trong `architecture.md`.

## Core libraries (one fixed choice per concern)
- TTS = **edge-tts** (`>=6.1.0`, async stream `Communicate`, SentenceBoundary → SRT). Đây là dependency runtime DUY NHẤT trong `requirements.txt`.
- Gen ảnh = **Codex CLI** (keyless, login ChatGPT Plus) gọi qua `subprocess` + STDIN. Backend ảnh DUY NHẤT của lớp plugin (anti2api/Gemini đã bị bỏ — xem git `0be1d20`).
- Ghép video = **ffmpeg + ffprobe** (gọi qua `subprocess`). Build phải có `libass` (filter `subtitles`/`zoompan`).
- Test = **pytest** + `unittest.mock` (chuẩn lib, không thêm plugin pytest).
- Path = **pathlib.Path** (không string). Type hints = `from __future__ import annotations`.

## External tools (NOT pip-installable — người dùng tự cài; `/video-doctor` kiểm)
- `ffmpeg` + `ffprobe` trong PATH (build có libass). `codex` CLI trong PATH + đã login. `python 3.11+`.

## Rules
- Do not add a new library outside the list above without comparing best practices via Context7 and updating this file.
- `vendor/videopipe/` là bản sao — KHÔNG `pip install` nó, KHÔNG sửa trực tiếp trừ khi đang chủ ý re-vendor (xem `architecture.md`).
- Khi engine gốc đổi: copy đè `*.py` + `script_schema.json` → chạy `python -m pytest tests/ -q` phải xanh → bump version `plugin.json` → ghi lý do re-vendor trong commit.

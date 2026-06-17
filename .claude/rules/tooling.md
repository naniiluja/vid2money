# Tooling (available skills / MCP / subagents — WHEN TO USE)

A catalog of this project's tools, with **when to use** each, so future-session agents can decide. Updated by `/ccf:ccf-updatespec` whenever a new tool is added.

## MCP servers
- **context7** — look up current docs for libraries/frameworks. **Use when:** cần API/best-practice/migration của edge-tts, ffmpeg, pytest, hay cấu trúc Claude Code plugin. How: `resolve-library-id` → `query-docs`.
- **microsoft-learn** — Microsoft/.NET/Azure docs. **Use when:** đụng nền tảng Microsoft (hiếm ở dự án này).

## Slash commands & skill dự án ship (artifact của plugin, không phải tool dev)
- **`/video-doctor`** → `skills/.../scripts/check_env.py --json`. **Use when:** cần chẩn đoán môi trường (ffmpeg/ffprobe/edge-tts/codex, STDIN fix), liệt kê blocker/warning. Chạy ĐẦU TIÊN khi nghi môi trường thiếu.
- **`/create-video <chủ đề>`** → nạp skill `video-storyteller`. **Use when:** tạo video: Claude viết storyboard → gọi `run_pipeline.py` → kiểm ảnh → báo `final.mp4`.
- **skill `video-storyteller`** (`SKILL.md`) — não điều phối từng bước (env → storyboard → pipeline → verify ảnh). Tham khảo khi sửa luồng điều phối.

## Scripts engine (gọi khi dev/test)
- `python -m pytest tests/ -q` — chạy test (mock I/O ngoài). Sau re-vendor PHẢI xanh.
- `python -m videopipe "<topic>"` — CLI engine độc lập (dev/debug, ngoài luồng plugin). Flags: `--storyboard`, `--run-id`, `--style`, `--voice`, `--music`, `--dry-run`, `-v`.
- `python "skills/video-storyteller/scripts/run_pipeline.py" --storyboard <json> --style <s> --music <mp3>` — wrapper plugin (set env + lazy import engine).

## Subagents (CCF)
- **ccf-implementer** — implement one task from the plan (has MCP). **Use when:** executing a task after /ccf-plan.
- **ccf-spec-checker** — review conformance/SOLID. **Use when:** /ccf-check.
- **ccf-debugger** — investigate one root-cause branch. **Use when:** /ccf-fix needs isolation.
- **ccf-best-practice-researcher** — fetch best practices. **Use when:** grounding a decision.

## System memory vs Spec (WHEN TO write where)
- **Spec** (this file + other rules): project rules derivable / thuộc repo. Lower weight (user message).
- **Memory** (`~/.claude/projects/<path>/memory/`): `feedback` anti-mistakes + `user` preferences. Higher weight (system prompt). Updated via `/ccf:ccf-updatespec`. **Do not duplicate** CLAUDE.md content.
- **MEMORY.md is a pure index** — chỉ ~200 dòng / 25KB đầu nạp mỗi session, giữ lean. Tier mạnh nhất là `feedback` (ghi win + loss kèm `Why` bắt buộc).

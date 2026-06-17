# video-storyteller (repo vid2money)

> Managed by **CCF (Claude Context First)**. Workflow: Explore → Plan → Implement → Commit.
> **STRICTLY SEQUENTIAL**: one task at a time, no parallel feature development.
> Ground every design decision in Context7 + Microsoft Learn.
> Keep this spec always fresh with `/ccf:ccf-updatespec`.

## What this is
Plugin Claude Code biến một chủ đề bất kỳ thành video kể chuyện / giải thích tiếng Anh hoàn chỉnh: `storyboard JSON → TTS (edge-tts) → ảnh AI (Codex CLI) → ghép ffmpeg → final.mp4 1080p`. Kiến trúc **2 lớp**: Claude là *orchestrator* (đọc command + SKILL.md, tự viết storyboard theo Pixar story spine, kiểm từng ảnh bằng mắt, gen lại nếu sai style), còn `vendor/videopipe/` là *engine* Python thực thi tuần tự TTS → ảnh → segment → assemble. Plugin **không tự cài** dependency và **không tự gen storyboard bằng script** trong luồng chính — Claude soạn storyboard, engine chỉ chấp hành. Cài 1 lần, dùng được ở bất kỳ project Claude Code nào.

## Repo layout (single package)
- git init ở root. Đây là **plugin một package**, KHÔNG phải monorepo — không có `be/`/`fe/`, không DB, không CI.
- `.claude-plugin/` — `plugin.json` (khai báo plugin) + `marketplace.json` (marketplace local).
- `commands/` — slash command: `create-video.md` (`/create-video <chủ đề>`), `video-doctor.md` (`/video-doctor`).
- `skills/video-storyteller/` — `SKILL.md` (não điều phối) + `scripts/` (`run_pipeline.py` wrapper, `check_env.py` probe) + `references/` (storyboard-craft, schema, styles).
- `vendor/videopipe/` — **bản sao điểm-thời-gian** của engine Python (KHÔNG tự sync với repo gốc). Re-vendor thủ công + bump version. Xem `architecture.md`.
- `assets/music/` — nhạc nền lofi mặc định + CREDITS. `stories/` — storyboard mẫu. `tests/` — pytest.

## Rules (imported — keep this file < 200 lines; detail lives in .claude/rules/)
@.claude/rules/tech-stack.md
@.claude/rules/architecture.md
@.claude/rules/coding-conventions.md
@.claude/rules/logging.md
@.claude/rules/testing.md
@.claude/rules/error-handling.md
@.claude/rules/debugging.md
@.claude/rules/tooling.md
@.claude/rules/git-workflow.md

## Current plan
Chưa có plan tuần tự. Khi bắt đầu việc mới, chạy `/ccf:ccf-plan` (trong plan mode) để sinh `.claude/plan/PLAN.md`. Thực thi **một task tại một thời điểm**, theo thứ tự; không bắt đầu task N+1 khi task N chưa implement + test + check xong.

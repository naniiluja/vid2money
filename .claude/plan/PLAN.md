# Implementation Plan — video-storyteller

> **Execution rule: STRICTLY SEQUENTIAL + VERTICAL SLICES.** Do exactly one task at a time, in order.
> Each task is a thin tracer-bullet crossing the layers it touches (engine + skill/SKILL.md + test + spec) — NOT a horizontal "all-engine-then-all-skill" phase.
> Do not start task N+1 until task N's **gate is GREEN** (implemented + tested + checked via `/ccf:ccf-check`).
> The `in-progress`/`in-review` status is read by the session-start hook to re-load context after compact — keep status up to date.

## Milestones
- **M1 — Dọn nền (S1–S3):** Codex-only, ngân sách thời lượng, nhịp nói best-practice. Không asset mới.
- **M2 — Nhạc cảm xúc (S4a–S4b):** engine mood/timeline/duck + bundle nhạc CC.
- **M3 — VFX hài (S5a–S5b):** engine VFX duration-preserving + bundle sticker doodle.

## Task backlog (in execution order)
| # | Slice | Layers | Gate (tests green) | Depends on | Status |
|---|-------|--------|--------------------|-----------|--------|
| 001 | Purge backend thừa → Codex-only | engine + skill/check_env + spec + test | pytest xanh + grep purge (allowlist) rỗng | — | in-review |
| 002 | Ngân sách `--target-minutes` | engine + cli/wrapper + SKILL + spec + test | unit xanh + `--dry-run` in target | 001 | in-review |
| 003 | TTS rate +5% + voice Andrew + nhấn nhá | engine + references/SKILL + test | unit xanh (rate & voice default) | 002 | in-review |
| 004 | Engine nhạc theo cảm xúc (logic + mix) | engine + schema/SKILL + test | unit + integration desync ≤1/fps (fixture) | 003 | in-review |
| 005 | Bundle nhạc CC + bật emotion mode | assets + SKILL + test | unit + integration thật ≤1/fps | 004 | todo |
| 006 | Engine VFX hài (builder + apply + flag) | engine + schema/cli/SKILL + test | unit + integration duration-preserving | 005 | todo |
| 007 | Bundle sticker doodle VFX | assets + test | unit (ref file tồn tại) + manual | 006 | todo |

> Status: `todo` / `in-progress` / `in-review` / `done` / `blocked`. Lifecycle: `todo → in-progress → in-review → done`. `ccf-implementer` marks `in-review` when code+test are complete; only `/ccf:ccf-updatespec` writes `done` after `/ccf:ccf-check` + `/code-review` pass.
> Per-task detail in `task-NNN-*.md`. Plan gốc đã duyệt: nội dung 7 slice + best-practice + review dispositions.
> **Asset slice (005, 007): duyệt nguồn/license nhạc & PNG với người dùng TRƯỚC khi mở session implementer.**
> **⚠️ BLOCKER môi trường:** ffmpeg/ffprobe KHÔNG có trong PATH máy hiện tại → gác **integration desync tường minh** của 004 (và 006) bị `skipif`, CHƯA verify thực tế. Unit logic xanh. Phải chạy lại các integration test này trên môi trường có ffmpeg trước khi coi 004/006 thực sự `done`.

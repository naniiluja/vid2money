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
| 001 | Purge backend thừa → Codex-only | engine + skill/check_env + spec + test | pytest xanh + grep purge (allowlist) rỗng | — | done |
| 002 | Ngân sách `--target-minutes` | engine + cli/wrapper + SKILL + spec + test | unit xanh + `--dry-run` in target | 001 | done |
| 003 | TTS rate +5% + voice Andrew + nhấn nhá | engine + references/SKILL + test | unit xanh (rate & voice default) | 002 | done |
| 004 | Engine nhạc theo cảm xúc (logic + mix) | engine + schema/SKILL + test | unit + integration desync ≤1/fps (fixture) | 003 | in-review |
| 005 | Bundle nhạc CC + bật emotion mode | assets + SKILL + test | unit + integration thật ≤1/fps | 004 | in-review |
| 006 | Engine VFX hài (builder + apply + flag) | engine + schema/cli/SKILL + test | unit + integration duration-preserving | 005 | in-review |
| 007 | Bundle sticker doodle VFX | assets + test | unit (ref file tồn tại) + manual | 006 | in-review |

> Status: `todo` / `in-progress` / `in-review` / `done` / `blocked`. Lifecycle: `todo → in-progress → in-review → done`. `ccf-implementer` marks `in-review` when code+test are complete; only `/ccf:ccf-updatespec` writes `done` after `/ccf:ccf-check` + `/code-review` pass.
> Per-task detail in `task-NNN-*.md`. Plan gốc đã duyệt: nội dung 7 slice + best-practice + review dispositions.
> **Asset slice (005, 007): duyệt nguồn/license nhạc & PNG với người dùng TRƯỚC khi mở session implementer.**
> **⚠️ Điều kiện cứng để `done` các slice còn `in-review`:**
> - **004, 006:** chạy 4 integration test (desync acrossfade + duration-preserving VFX) XANH trên môi trường có ffmpeg (hiện `skipif`, CHƯA verify).
> - **005:** đủ 6/6 mood có `.mp3` thật (hiện 2/6; 4 mood còn `SOURCE.txt` do Pixabay CDN 403 — ngài drop file thủ công) + integration mix thật.
> - **007:** PNG sticker hiện là **orphan asset** — `vfx type=emoji` dùng `drawtext` unicode, CHƯA có `vfx type=overlay` ref PNG trong engine. Cần implement `overlay` type rồi wire test ref-file.
> - Wiring nhạc cảm xúc (`--music-library`/`--music-mode`) + lookup path `<mood>/*.mp3` đã được sửa sau `/ccf-check` (bug làm M2 chết im lặng); có `tests/test_music_wiring.py` gác.

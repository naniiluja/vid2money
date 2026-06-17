# Task 006 — Engine VFX hài (builder + apply + flag)

- **Vertical slice:** engine (`vfx.py`/`ffmpeg_ops.py`/`config.py`) + cli/wrapper + schema/SKILL + test
- **Depends on:** 005
- **Spec refs:** `.claude/rules/error-handling.md` (duration-preserving, raise đúng chỗ), `.claude/rules/architecture.md` (env-before-import, 1 trách nhiệm)
- **Implemented by:** ccf-implementer (+ Context7 cho drawtext/zoompan/overlay)
- **Gate (must be GREEN before the next slice):** unit xanh **+ integration: segment có-vfx vs không-vfx → `ffprobe` duration chênh ≤ 1/fps** (bất biến duration-preserving, tường minh)

## Goal (one sentence)
Lớp VFX hài tiết chế hợp style doodle, bật/tắt qua flag, đảm bảo KHÔNG đổi duration (không desync).

## Acceptance criteria (verifiable)
- [ ] `build_vfx_filters(annotations, enabled=False)` → `""` (passthrough).
- [ ] Mọi effect chứa `enable='between(t,a,b)'`; `zoompan` dùng `d=1`.
- [ ] Annotation dùng `setpts` → raise (guard duration).
- [ ] Cap ≤3 beat/shot; audio `-c:a copy`.
- [ ] `--vfx` plumb qua wrapper KHÔNG kéo import sớm `videopipe`.

## Test first (write before implementing)
- unit `build_vfx_filters`: (a) tắt→`""`; (b) mọi effect có `enable='between'`; (c) zoompan `d=1`; (d) `setpts`→raise; (e) ≤3 beat/shot.
- integration: segment có-vfx vs không-vfx → `ffprobe` duration bằng nhau (≤1/fps).

## Files to touch
- **MỚI** `vendor/videopipe/vfx.py` — `build_vfx_filters`; bộ drawtext pop / zoompan punch (d=1) / crop-shake sin / overlay PNG; guard `setpts`.
- `vendor/videopipe/ffmpeg_ops.py` — chèn vfx lúc dựng segment; audio copy; cap beat.
- `vendor/videopipe/config.py` — `vfx_enabled: bool = False`. `cli.py` + `run_pipeline.py` — cờ `--vfx`.
- `skills/.../references/storyboard.schema.json` — field tuỳ chọn `vfx` mỗi shot; `SKILL.md` — gắn TIẾT CHẾ ở câu chốt (≤2–3/phút).

## Steps (thin end-to-end slice)
1. Viết failing test (builder branches + duration-preserving integration).
2. Implement vfx.py + ffmpeg apply + config/cli + schema/SKILL.
3. Gác XANH (unit + integration duration-preserving) → `in-review`.
4. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- "punctuation, not decoration", ≤2–3 beat/phút, hit frame cuối câu chốt, 0.3–0.5s, rule-of-three (FFmpeg timeline expressions; motion design).
- Tất cả `enable='between'` → giữ frame count; `zoompan d=1` bắt buộc; `setpts` đổi duration → cấm inline.

# Task 002 — Ngân sách thời lượng `--target-minutes`

- **Vertical slice:** engine (`config.py`/`pipeline.py`) + cli/wrapper + skill (SKILL/storyboard-craft) + spec (architecture.md) + test
- **Depends on:** 001
- **Spec refs:** `.claude/rules/architecture.md` (env-before-import, target-minutes), `.claude/rules/tech-stack.md`
- **Implemented by:** ccf-implementer (+ Context7 cho argparse nếu cần)
- **Gate (must be GREEN before the next slice):** unit xanh + `python -m videopipe --dry-run --target-minutes 10` in target qua `config.describe()`

## Goal (one sentence)
Cho ngài chỉ định `--target-minutes N` → output ≈ N phút (±10%), với ngân sách wpm dẫn xuất từ rate (không magic constant) và cảnh báo khi lệch.

## Acceptance criteria (verifiable)
- [ ] `words_per_minute("+5%") ≈ 157.5` (dẫn xuất từ `BASE_WPM=150`).
- [ ] `expected_words(minutes, rate) = round(minutes * wpm * 0.88)`.
- [ ] `is_duration_off(actual, target, tol=0.10)` đúng ở biên (±10% pass, ±11% trigger).
- [ ] `--target-minutes` plumb qua wrapper KHÔNG kéo import sớm `videopipe`.
- [ ] Sau assemble, pipeline cảnh báo nếu thực tế lệch target >10%.

## Test first (write before implementing)
- unit `words_per_minute("+5%")` ≈ 157.5; vài rate khác.
- unit `expected_words` vài mốc (1/3/10 phút theo rate).
- unit `is_duration_off` ở biên ±10%/±11%.

## Files to touch
- `vendor/videopipe/config.py` — `target_minutes: float|None`; `BASE_WPM=150`; `words_per_minute(rate)`; `expected_words(minutes, rate)`; `is_duration_off(actual, target, tol)`.
- `vendor/videopipe/cli.py` + `skills/video-storyteller/scripts/run_pipeline.py` — cờ `--target-minutes` (giữ env-before-import).
- `vendor/videopipe/pipeline.py` — sau assemble, probe `final.mp4`, cảnh báo nếu lệch.
- `skills/video-storyteller/SKILL.md` Bước 3 + `references/storyboard-craft.md` — thay "8–14 shot (2–4 phút)" bằng ngân sách lời `phút × wpm × 0.88`, shot ≈ `tổng_giây/18–22s`.
- `.claude/rules/architecture.md:5` — bỏ "8–14 shot", mô tả cơ chế ngân sách (spec-sync).

## Steps (thin end-to-end slice)
1. Viết failing test (wpm/budget/off-check).
2. Implement config helpers + flag + post-assemble warn + SKILL/spec sync.
3. Gác XANH (unit + dry-run) → `in-review`.
4. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- ~150 wpm hội thoại; 140–160 explainer; `+5%`≈157 wpm (Breadn Beyond; Souza & Turner 2014; MS Learn TTS WPM).
- Coupling S2↔S3: wpm dẫn xuất từ rate → khử dương-tính-giả khi 002 xong mà 003 chưa (engine còn -4% → video DÀI hơn target = an toàn).

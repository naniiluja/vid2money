# Task 003 — TTS nhịp nhanh hơn + nhấn nhá

- **Vertical slice:** engine (`config.py`/`tts.py`) + skill (references/SKILL) + test
- **Depends on:** 002
- **Spec refs:** `.claude/rules/tech-stack.md` (edge-tts), `.claude/rules/error-handling.md` (retry transient)
- **Implemented by:** ccf-implementer
- **Gate (must be GREEN before the next slice):** unit xanh (rate & voice default đồng bộ)

## Goal (one sentence)
Tăng nhịp nói lên ~157 wpm tự nhiên + hướng dẫn nhấn nhá không-SSML, đồng bộ cả rate VÀ voice giữa config và tts.

## Acceptance criteria (verifiable)
- [ ] `PipelineConfig().tts_rate == "+5%"`.
- [ ] `synthesize` default `rate == "+5%"` và `voice == "en-US-AndrewMultilingualNeural"`.
- [ ] SKILL/storyboard-craft hướng dẫn nhấn nhá bằng `—`/`...`/`,` + CAPS (tiết chế).
- [ ] Tài liệu hoá: đổi rate ⇒ work-dir cũ invalid, cấm `--run-id` cũ qua ranh giới này.

## Test first (write before implementing)
- unit `PipelineConfig().tts_rate == "+5%"`.
- unit `synthesize` default `rate=="+5%"` & `voice=="en-US-AndrewMultilingualNeural"` (edge-tts mock — không gọi mạng).

## Files to touch
- `vendor/videopipe/config.py:112` — `tts_rate` `-4%` → `+5%`; comment + trích nguồn.
- `vendor/videopipe/tts.py:85` — default `rate` `-8%` → `+5%`; `tts.py:84` `voice` `en-US-GuyNeural` → `en-US-AndrewMultilingualNeural`.
- `skills/video-storyteller/references/storyboard-craft.md` + `SKILL.md` — nhấn nhá không-SSML + note resume invalid qua ranh giới rate.

## Steps (thin end-to-end slice)
1. Viết failing test (rate + voice default).
2. Đổi config + tts default + skill guidance + note resume.
3. Gác XANH (unit) → `in-review`.
4. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- edge-tts **KHÔNG nhận SSML** (`<emphasis>`/`<break>` strip) → nhấn nhá bằng dấu câu + CAPS, hoặc tách câu đổi rate (GitHub rany2/edge-tts; Context7).
- `+5%` ≈157 wpm khớp ngân sách task 002.

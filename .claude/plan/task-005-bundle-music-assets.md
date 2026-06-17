# Task 005 — Bundle nhạc CC + bật `music_mode=emotion`

- **Vertical slice:** assets (`assets/music/<mood>/`) + skill (SKILL) + test
- **Depends on:** 004
- **Spec refs:** `.claude/rules/git-workflow.md` (asset license), `.claude/rules/tech-stack.md`
- **Implemented by:** ccf-implementer **SAU khi ngài duyệt nguồn nhạc**
- **Gate (must be GREEN before the next slice):** unit (mỗi mood ≥1 file + CREDITS có entry) + integration thật `abs(ffprobe(final) − tổng_audio) ≤ 1/fps`

## ⚠️ Tiền điều kiện (giải finding H #2)
Nguồn + license từng track **quyết & xác nhận với người dùng TRƯỚC khi mở session implementer** — KHÔNG để bước tải file / quyết license trong luồng `ccf-implementer` tự động. Chọn file nhỏ, license rõ (Incompetech CC-BY / Pixabay), ghi CREDITS.

## Goal (one sentence)
Nạp thư viện nhạc thật theo 6 mood + để emotion là mặc định khi gọi pipeline qua SKILL.

## Acceptance criteria (verifiable)
- [ ] `assets/music/<mood>/` có ≥1 track CC nhỏ cho mỗi mood (6 mood).
- [ ] `assets/music/CREDITS.txt` có entry attribution mỗi track dùng.
- [ ] SKILL Bước 4 trỏ `--music-library` + `--music-mode emotion`.

## Test first (write before implementing)
- unit: mỗi mood trong taxonomy có ≥1 file trong library.
- unit: mỗi track dùng có entry trong CREDITS.

## Files to touch
- **MỚI** `assets/music/<mood>/*.mp3` (1–2 track CC/mood) + `assets/music/CREDITS.txt`.
- `skills/video-storyteller/SKILL.md` Bước 4 — `--music-library` + `--music-mode emotion`.

## Steps (thin end-to-end slice)
1. **Ngài duyệt nguồn/license nhạc** (ngoài session implementer tự động).
2. Viết failing test (mood↔file, CREDITS parity).
3. Nạp track + CREDITS + wire SKILL emotion-mode.
4. Gác XANH (unit + integration thật) → `in-review`.
5. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- Incompetech (CC-BY, ghi công bắt buộc), Pixabay (không bắt buộc), FMA/YouTube Audio Library (tuỳ track) — Incompetech FAQ; Pixabay License.
- Tải nhạc về repo = thao tác mạng + dung lượng → xin xác nhận, file nhỏ.

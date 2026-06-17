# Task 007 — Bundle sticker doodle VFX

- **Vertical slice:** assets (`assets/vfx/`) + test
- **Depends on:** 006
- **Spec refs:** `.claude/rules/git-workflow.md` (asset license)
- **Implemented by:** ccf-implementer **SAU khi ngài duyệt nguồn PNG**
- **Gate (đóng plan):** unit (mỗi `vfx type=emoji` ref file tồn tại) + manual: 1 clip có sticker hợp style

## ⚠️ Tiền điều kiện
Nguồn + license PNG **quyết & xác nhận với người dùng TRƯỚC** khi mở implementer (cùng lý do task 005).

## Goal (one sentence)
Nạp vài sticker doodle PNG có alpha cho overlay emoji của VFX.

## Acceptance criteria (verifiable)
- [ ] `assets/vfx/*.png` (sticker doodle alpha) đủ cho các `vfx type=emoji` SKILL gợi ý.
- [ ] CREDITS nếu nguồn yêu cầu attribution.
- [ ] Mỗi `vfx type=emoji` trong schema/SKILL tham chiếu được file tồn tại.

## Test first (write before implementing)
- unit: mỗi `vfx type=emoji` ref được file tồn tại trong `assets/vfx/`.

## Files to touch
- **MỚI** `assets/vfx/*.png` (sticker doodle alpha) + CREDITS nếu cần.

## Steps (thin end-to-end slice)
1. **Ngài duyệt nguồn/license PNG** (ngoài session implementer tự động).
2. Viết failing test (ref file tồn tại).
3. Nạp PNG + CREDITS.
4. Gác XANH (unit) + manual verify → `in-review`.
5. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- Sticker doodle hợp style stick-figure/whiteboard; alpha channel cho `overlay`.
- Tải asset = thao tác mạng → xin xác nhận, file nhỏ.

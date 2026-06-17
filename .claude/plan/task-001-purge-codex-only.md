# Task 001 — Purge backend thừa → Codex-only

- **Vertical slice:** engine (`images.py`/`config.py`) + skill (`check_env.py`) + spec (rules/skill/README sync) + test
- **Depends on:** — (slice đầu)
- **Spec refs:** `.claude/rules/tech-stack.md` (Codex là backend ảnh duy nhất), `.claude/rules/architecture.md` (1 trách nhiệm/module), `.claude/rules/coding-conventions.md`
- **Implemented by:** ccf-implementer (không cần MCP)
- **Gate (must be GREEN before the next slice):** `python -m pytest tests/ -q` xanh + `grep -ri "backend_cũ" . | grep -vE '(\.git/|tech-stack\.md|git-workflow\.md|cached-tickling-bunny)'` **rỗng** (xem gate thực tế trong PLAN.md)

## Goal (one sentence)
Xoá sạch code chết backend ảnh cũ để chỉ còn Codex — style nhất quán tuyệt đối, không chỗ nào còn nhắc 2-backend.

## Acceptance criteria (verifiable)
- [x] `images.py` không còn hàm gen backend cũ, helper build payload, constants backend cũ, nhánh `if backend == "<cũ>"`.
- [x] `config.py` bỏ comment + field-handling backend cũ; `image_backend` giản lược về codex.
- [x] grep purge (có allowlist 2 file lịch sử) rỗng toàn repo.
- [x] `check_env`/`test_check_env` còn `recommended_backend == codex`; mọi test cũ vẫn xanh.

## Test first (write before implementing)
- Test: `images.py` không chứa token backend cũ (đọc nguồn, assert).
- Test: `generate_image()` chỉ route Codex (mock `subprocess.run`).
- Test cũ `test_check_env.py` giữ xanh sau khi giản lược assertion dư thừa.

## Files to touch
- `vendor/videopipe/images.py` — xoá toàn bộ nhánh + helper backend cũ; chỉ giữ Codex.
- `vendor/videopipe/config.py:104-107` — bỏ comment + field-handling backend cũ. **KHÔNG đụng `cli.py` cho backend — flag `--backend` KHÔNG tồn tại** (cli.py chỉ có `--style`...); `image_backend` là field config đọc ở `pipeline.py:137/160/231/263`.
- `skills/video-storyteller/scripts/check_env.py` + `tests/test_check_env.py` — giản lược assertion backend cũ dư thừa.
- Spec/skill sync: grep toàn repo → dọn, **TRỪ allowlist** `tech-stack.md:13` + `git-workflow.md:14` (lịch sử có chủ đích — giữ nguyên). Cập nhật `.claude/rules/architecture.md:27` nếu chữ ký engine đổi.

## Steps (thin end-to-end slice)
1. Viết failing test (không-token backend cũ + route codex).
2. Purge engine + spec/skill sync.
3. Chạy gác (pytest + grep allowlist) — phải XANH → đánh `in-review`.
4. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec` (mới ghi `done`).

## Notes / best-practice sources
- Refactor thuần (không feature) — tách riêng đúng luật CCF. Đây là cleanup, không đổi hành vi Codex.
- Allowlist 2 file lịch sử để gác grep không đỏ vĩnh viễn (ccf-spec-checker vòng 2 H-finding).

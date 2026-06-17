# Git Workflow

## Most important rule
- **Do NOT commit/push unless the user explicitly asks.** Every git operation must be confirmed first.

## Commit attribution (harness-enforced)
- Attribution is enforced by `.claude/settings.json` `attribution` (`{ "commit": "...", "pr": "..." }`), per `code.claude.com/docs/en/settings`. Settings deterministic và **supersede** narrative.
- Lịch sử repo: commit subject-only, **KHÔNG có** Co-Authored-By / Generated-with trailer → `attribution.commit` và `attribution.pr` đều `""` (suppress). Đừng tự thêm trailer bằng tay.

## When asked to commit
- Nếu đang trên branch mặc định (`master`): tạo branch mới trước.
- Commit message theo convention repo: **`<type>: <mô tả tiếng Việt>`** — conventional-commit, message tiếng Việt, KHÔNG có scope, KHÔNG body/trailer (subject-only).
  - `type` ∈ `{feat, fix, refactor, docs, chore}` (quan sát: feat/fix/refactor/docs; dùng `chore:` cho re-vendor).
  - Ví dụ thực tế: `fix: _probe_anti2api coi HTTP 404/401 là server sống`, `refactor: bỏ backend anti2api/Gemini khỏi lớp plugin, chỉ còn Codex`, `docs: hướng dẫn cài plugin từ GitHub (HTTPS) tránh lỗi SSH`.
- One logical change per commit; không gộp việc không liên quan.
- Re-vendor engine: dùng `chore: re-vendor videopipe <ngày> — <lý do ngắn>` và bump version `plugin.json` cùng commit.

## Branch & PR
- Branch naming: lịch sử chỉ có `master` (linear, không feature branch). Khi cần branch: dùng tên ngắn mô tả việc (vd `fix-codex-stdin`); xác nhận với ngài nếu chưa chắc.
- PR rules: chưa có tiền lệ PR / không có CI. Nếu mở PR: tiêu đề theo cùng convention commit, body tiếng Việt, KHÔNG trailer attribution.

## Single package
- git ở root duy nhất; đây không phải monorepo — không git init trong sub-folder.

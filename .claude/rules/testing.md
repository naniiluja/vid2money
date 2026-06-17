# Testing (verification-first)

Philosophy: **write a failing test FIRST** before implementing/fixing — this is the single highest-leverage thing to let Claude verify its own work.

## Rules
- Each task: write a test reproducing the acceptance criteria (red) → implement → test green.
- Bug fix: write a test reproducing the bug (red) first, then fix.
- A task's acceptance criteria = concrete tests, not vague descriptions.
- **Mock toàn bộ I/O ngoài** (ffmpeg, edge-tts, Codex CLI, `run_storyboard`) — test KHÔNG được gọi tool/mạng thật. Pattern hiện có: `monkeypatch`/`unittest.mock` cho `shutil.which`, `importlib.util.find_spec`, `subprocess`, `videopipe.pipeline.run_storyboard`.
- Tách hàm thuần / `_resolve_paths` / `_build_config` ra để test được mà không cần import engine nặng.

## Tooling & location
- Test framework: **pytest** + `unittest.mock` (không thêm plugin pytest; không có `pytest.ini`).
- Run command: `python -m pytest tests/ -q` (Windows: chạy qua PowerShell).
- Tests live in: `tests/` ở root (`test_check_env.py`, `test_run_pipeline.py`).

## Coverage
- Coverage target: không có ngưỡng số cứng. Bao phủ các đường nghiệp vụ lõi: probe môi trường (Codex-only, blockers, cảnh báo Windows), giải path + dựng config + luồng `main()` của wrapper.
- Core business paths must have tests before marking a task `done`.
- Sau khi re-vendor engine: `python -m pytest tests/ -q` PHẢI xanh hoàn toàn trước khi bump version.

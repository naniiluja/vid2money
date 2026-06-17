# Architecture

## Layering & boundaries
Hai lớp tách bạch:
- **Lớp điều phối (Claude)**: `commands/*.md` → `skills/video-storyteller/SKILL.md`. Claude tự viết storyboard JSON (Pixar story spine). Số shot và ngân sách lời dẫn xuất từ `--target-minutes` nếu được đặt: ngân sách từ = `phút × wpm × 0.88` (wpm = `BASE_WPM × (1 + rate%)`), số shot ≈ `(phút × 60) / 18–22s`; nếu không đặt mặc định 8–14 shot (~2–4 phút). Phán xét chất lượng ảnh bằng mắt, quyết định gen lại. Đây là "não".
- **Lớp engine (videopipe)**: `vendor/videopipe/` thực thi tuần tự. KHÔNG ra quyết định sáng tạo — chỉ chấp hành storyboard đã có. Đây là "tay chân".
- **Cầu nối**: `skills/video-storyteller/scripts/run_pipeline.py` — set env (`VIDEOPIPE_WORK_ROOT`, `VIDEOPIPE_ASSETS_ROOT`) → `sys.path.insert(vendor)` → **lazy import** `videopipe.pipeline.run_storyboard()`.

## Dependency direction
- Một chiều: `command.md → SKILL.md → run_pipeline.py → videopipe.pipeline → {config, storyboard, tts, images, ffmpeg_ops}`.
- `pipeline.py` là orchestrator; nó gọi các module con, KHÔNG có chiều ngược lại (module con không import pipeline).
- `script_gen.py` + `research.py` (mode `--from-trending` của CLI độc lập) KHÔNG nằm trong luồng plugin — Claude tự viết storyboard thay cho chúng.

## Design patterns
- **Orchestrator + Engine**: Claude điều phối, videopipe chấp hành (xem trên).
- **Dependency Injection qua env var (đọc lazy)**: `config.py` đọc `VIDEOPIPE_WORK_ROOT`/`VIDEOPIPE_ASSETS_ROOT` tại thời điểm *truy cập property*, KHÔNG lúc import — để wrapper set env SAU khi module nạp (giải import-timing seam). KHÔNG phá vỡ thứ tự này: set env TRƯỚC khi import videopipe.
- **Resume-friendly qua filesystem**: pipeline skip artifact đã tồn tại (tts: `scene_N.mp3` + `scene_N.srt` cùng có; image: `out_path.exists() and size>0`; segment: `seg_N.mp4` tồn tại). Card + assemble luôn tạo lại (nhỏ/nhanh).
- **Partial-file pattern**: ffmpeg ghi `.partial` rồi rename khi thành công; lỗi → xoá `.partial` để resume không thấy artifact cụt (`ffmpeg_ops.py`).
- **Neutral cwd cho Codex**: gen ảnh từ `~/.codex/_imagegen_cwd` (dọn ảnh cũ + AGENTS.md rỗng) để chống context-bleed.

## Where things go
- Storyboard JSON Claude viết → `<cwd>/video-out/<slug>.json`.
- Artifact engine → `work/<run-id>/`: `style_sheet.png`, `scene_N.{mp3,srt,png}` (multi-image: `scene_N_k.png`), `seg_N.mp4`, `seg_title.mp4`, `seg_end.mp4`, `full_audio.mp3`, `full.srt`, `final.mp4`.
- `run_id` = `{timestamp}-{topic_slug}`. Cùng `--run-id` cũ → resume.

## Re-vendor (engine là bản sao điểm-thời-gian)
`vendor/videopipe/` KHÔNG tự sync. Khi engine gốc đổi: (1) copy đè `*.py` + `script_schema.json`; (2) `python -m pytest tests/ -q` phải xanh; (3) bump version `plugin.json`; (4) commit `chore: re-vendor ...` ghi lý do; (5) chạy `/video-doctor` xác nhận `images.py` còn STDIN fix.

## Verifiable rules
- Mỗi module một trách nhiệm: `tts.py`=giọng+SRT, `images.py`=ảnh, `ffmpeg_ops.py`=ghép, `config.py`=path+tham số, `storyboard.py`=load JSON, `pipeline.py`=điều phối.
- Không circular import giữa các lớp/module.
- KHÔNG set env videopipe SAU khi đã import nó (lazy read chỉ cứu được nếu env có lúc property được gọi).

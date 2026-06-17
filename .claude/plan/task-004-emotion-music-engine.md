# Task 004 — Engine nhạc theo cảm xúc (logic + mix)

- **Vertical slice:** engine (`music.py`/`ffmpeg_ops.py`/`pipeline.py`/`config.py`) + schema/SKILL + test
- **Depends on:** 003
- **Spec refs:** `.claude/rules/architecture.md` (Claude quyết, engine chấp hành), `.claude/rules/error-handling.md` (desync = warning), `.claude/rules/logging.md`
- **Implemented by:** ccf-implementer (+ Context7 cho filter_complex ffmpeg)
- **Gate (must be GREEN before the next slice):** unit xanh **+ integration desync `abs(ffprobe(final) − tổng_audio_dự_kiến) ≤ 1/fps` bằng fixture mp3 synthetic** (≥2 mối acrossfade)

## Goal (one sentence)
Engine chọn mood mỗi shot, dựng music timeline đổi track theo đoạn, duck động dưới giọng — test bằng fixture synthetic, KHÔNG phụ thuộc bước tải nhạc.

## Acceptance criteria (verifiable)
- [ ] `resolve_mood`: ưu tiên `shot.mood` hợp lệ; nhãn sai → fallback keyword; "khủng hoảng"→tense; rỗng→calm.
- [ ] `build_music_timeline`: gộp mood liền kề; điểm cắt = ranh giới shot; tổng thời lượng khớp.
- [ ] enum `mood` trong `storyboard.schema.json` == taxonomy trong `music.py` (single source of truth).
- [ ] `music_mode="static"` giữ nguyên hành vi duck cũ.
- [ ] filter_complex `acrossfade`(d=2,c=exp) + `sidechaincompress` well-formed; **không desync** (gác tường minh).

## Test first (write before implementing)
- unit `resolve_mood` (các nhánh trên).
- unit `build_music_timeline` (gộp/cắt/tổng) — ffmpeg mock.
- unit single-source-of-truth: schema enum == `music.py` taxonomy.
- integration: run 2-scene khác mood (fixture mp3 synthetic) → `abs(ffprobe(final) − tổng_audio_dự_kiến) ≤ 1/fps`. **Công thức:** `tổng = Σdur_shot − Σoverlap_crossfade` (acrossfade ăn `d` giây/mối nối).

## Files to touch
- **MỚI** `vendor/videopipe/music.py` — taxonomy 6 mood; `resolve_mood`; `build_music_timeline`.
- `vendor/videopipe/ffmpeg_ops.py` — mix `atrim`+`acrossfade`+`sidechaincompress`; giữ static-duck fallback.
- `vendor/videopipe/config.py` — `music_mode: "static"|"emotion"="static"`; `music_library: Path|None`.
- `vendor/videopipe/pipeline.py` — mood mỗi shot → timeline → assemble.
- `skills/.../references/storyboard.schema.json` — field tuỳ chọn `mood` (enum 6); `SKILL.md` hướng dẫn Claude gán.

## Steps (thin end-to-end slice)
1. Viết failing test (resolve_mood/timeline/enum-parity/desync-integration).
2. Implement music.py + ffmpeg mix + config + pipeline + schema/SKILL.
3. Gác XANH (unit + integration desync tường minh) → `in-review`.
4. `/ccf:ccf-check` → `/code-review` → `/ccf:ccf-updatespec`.

## Notes / best-practice sources
- Russell valence-arousal → 6 mood (calm/uplifting/tense/somber/playful/triumphant) + BPM/tonality/keyword (PsychologyFanatic; EMOPIA; PMC tempo).
- `acrossfade` d=2 curve exp; `sidechaincompress` threshold=0.02/ratio=8/attack=5/release=200; điểm cắt mood trùng cuối câu (FFmpeg docs; ffmpeg-user list).
- **Desync H-finding:** gác assert tường minh, độc lập `pipeline.py:280-283` (nó nuốt ValueError→warning).

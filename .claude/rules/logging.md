# Logging

Engine media-pipeline (không phải web request), nên "correlation" ở đây là **run_id** + tên stage có đánh số, để grep được trace một lần chạy.

## Hiện trạng (đúng codebase)
- Logger dùng chung tên `"videopipe"` ở mọi module (`pipeline.py`, `tts.py`, `images.py`, `ffmpeg_ops.py`, `script_gen.py`, `research.py`). Wrapper thêm `"videopipe.runner"`.
- `basicConfig` trong `run_pipeline.py`: `level=INFO`, `format="%(levelname)s %(name)s: %(message)s"`, `stream=sys.stderr`.
- **stdout chỉ in path `final.mp4`** (1 dòng) — caller parse được; mọi log khác đi stderr.
- Message tiếng Việt. Stage có prefix đánh số: `[1] research`, `[2] script`, `[3-5] scene N xong (…s)`, `[6] assemble`, `shot N/M xong (…s, K ảnh)`.
- `-v/--verbose` → DEBUG (in full ffmpeg cmd, font resolution, payload repr).

## Log levels
- `warning`: bất thường nhưng đã xử lý — retry TTS/Codex, timeout-rồi-thử-lại, **desync (tiếp tục không raise)**, codex exit ≠ 0.
- `info`: mốc nghiệp vụ — stage xong, duration, path artifact, skip-resume.
- `debug`: chi tiết phát triển — ffmpeg cmd, font, silent audio, payload.
- Không log secret/PII (Codex keyless, edge-tts không key — rủi ro thấp nhưng vẫn không in token nếu sau này thêm).

## Quy ước khi thêm log mới
- Giữ logger name `"videopipe"`; message tiếng Việt; stage giữ prefix đánh số `[k]` hoặc `shot N/M`.
- Khi thao tác liên quan một run cụ thể, nhắc `run_id` hoặc tên artifact trong message để grep được (log hiện CHƯA nhúng run_id vào format — đây là hạn chế đã biết, đừng giả định nó có sẵn).
- stderr cho log, stdout chỉ cho kết quả máy-đọc (path).

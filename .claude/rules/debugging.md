# Debugging (disciplined, no rushing)

Mandatory process when investigating a bug (used by `/ccf:ccf-fix`):
1. **Reproduce** — tái hiện từ triệu chứng/input/môi trường trước khi đụng code. Với pipeline: ghi lại `run_id`, storyboard JSON, style, OS.
2. **Trace step by step** — đọc log stderr theo stage đánh số (`[1]`→`[6]`, `shot N/M`); chạy lại với `-v/--verbose` để có DEBUG (ffmpeg cmd, font, payload).
3. **Kiểm artifact filesystem read-only** — soi `work/<run-id>/`: thiếu/0-byte `scene_N.png`? `seg_N.mp4` có không? `full.srt` offset đúng? (Đây là "DB" của dự án — không có MCP DB.)
4. **Isolate with evidence** — khoanh vùng bằng file:line / dòng log / artifact cụ thể, không cảm tính.
5. **Failing test** — viết test tái hiện bug (red) trước, mock I/O ngoài.
6. **Minimal fix** — chỉ sửa trong phạm vi, không refactor kèm.

> Never guess and fix on the spot before you have evidence.

## Mẹo theo tầng (đặc thù dự án)
- **Ảnh sai style (context-bleed Codex/Windows)**: kiểm `images.py` còn STDIN fix (`input=` + `-` positional) qua `/video-doctor`; xoá `scene_N.png` sai rồi chạy lại cùng `--run-id` (resume gen lại ảnh thiếu).
- **Phụ đề lệch giọng**: kiểm offset SRT — bật `show_title_card` cộng `intro_seconds` vào mọi timestamp (coupling ẩn); xoá `seg_N.mp4` rồi rerun.
- **Resume bỏ qua nhầm**: TTS skip cần CẢ `scene_N.mp3` + `scene_N.srt`; nếu crash sau khi ghi mp3 trước srt → lần sau vẫn gen lại (đúng). Image skip chỉ check `size>0`, KHÔNG check ảnh hỏng — nghi ảnh hỏng thì xoá tay.
- **Re-vendor làm vỡ test**: `git diff` so engine gốc; chạy `python -m pytest tests/ -q`.

## Known bugs (updated by /ccf:ccf-updatespec)
- (chưa có mục nào)
<!-- Each entry: symptom — root cause — how to prevent — related files -->

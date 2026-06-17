# Error Handling

## Taxonomy
- **Lỗi nghiệp vụ mong đợi**: thiếu tool (ffmpeg/ffprobe/codex không trong PATH), build ffmpeg thiếu libass, edge-tts lỗi mạng, storyboard không hợp lệ → báo rõ ràng, hướng dẫn người dùng (`/video-doctor` liệt kê blocker/warning).
- **Lỗi hệ thống**: bug logic, subprocess exit ≠ 0 ngoài dự kiến → `RuntimeError` kèm context (stderr tail).

## Verifiable rules
- **No silent catch.** Lỗi bắt được phải log (kèm run_id/tên artifact nếu có) hoặc re-raise kèm context. Tuyệt đối không `except: pass`.
- Bọc lỗi kèm context khi qua boundary: subprocess fail → `RuntimeError` đính `cmd` + `stderr[-500:]`, KHÔNG nuốt stack gốc.
- **Retry chỉ lỗi transient** (mạng/timeout) có backoff; KHÔNG retry lỗi nghiệp vụ:
  - edge-tts: max 3 lần, backoff `2^(attempt-1)`s, chỉ retry transient (`ClientConnectionError`, `ServerTimeoutError`, `TimeoutError`, `ConnectionError`, `OSError`); `ValueError`/voice sai → fail-fast.
  - Codex gen ảnh: 3 lần + timeout; sau timeout vẫn kiểm `_newest_image_since` (ảnh có thể đã sinh) trước khi coi là fail.
- **Desync là warning, KHÔNG raise**: `assert_duration_match` lệch ≤ 1 frame → bỏ qua (codec rounding); lệch lớn → `log.warning("shot N/M desync (tiếp tục)")` và pipeline tiếp tục. Đây là chủ ý — đừng "sửa" thành raise.
- **Partial-file**: ffmpeg ghi `.partial` → rename khi xong; lỗi → xoá `.partial` để resume không thấy artifact cụt.

## Error format
- Kiểu lỗi chuẩn: `RuntimeError` với message tiếng Việt, rõ nguyên nhân + cách khắc phục. Không có HTTP status (không phải web service).
- Lỗi tool thiếu: nêu rõ tool nào + cách cài (giống README "Khắc phục sự cố").

---
description: Kiểm tra môi trường cài đặt video-storyteller — tool nào có/thiếu, backend khuyên dùng, blocker, cảnh báo.
---

# /video-doctor — Chẩn đoán môi trường

Khi người dùng gọi lệnh này, hãy thực hiện các bước sau:

## Bước 1 — Chạy check_env.py

Chạy lệnh sau và thu thập JSON output:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/scripts/check_env.py" --json
```

Nếu `${CLAUDE_PLUGIN_ROOT}` chưa được set, thử đường dẫn tương đối từ plugin root.

## Bước 2 — Parse và báo cáo

Parse JSON trả về (các field: `tools`, `recommended_backend`, `blockers`, `warnings`) và trình bày rõ ràng:

### Công cụ
Liệt kê từng công cụ trong `tools`:
- `ffmpeg`, `ffprobe`, `codex`, `edge-tts` — có (✓) hay thiếu (✗).

### Backend ảnh
`recommended_backend` luôn = `"codex"` — Codex CLI là backend ảnh duy nhất của plugin (keyless, cần login ChatGPT Plus). Nhắc người dùng kiểm tra ảnh kỹ sau khi gen (xem cảnh báo Windows bên dưới).

### Blockers
Nếu `blockers` không rỗng:
- Nói rõ **pipeline CHƯA chạy được** vì thiếu công cụ bắt buộc.
- Với mỗi blocker: trích dẫn thông báo lỗi + hướng dẫn cài đặt:
  - Thiếu `ffmpeg`/`ffprobe`: cài từ https://ffmpeg.org/download.html, thêm vào PATH.
  - Thiếu `edge-tts`: chạy `pip install edge-tts>=6.1.0`.

Nếu `blockers` rỗng: xác nhận pipeline sẵn sàng chạy.

### Cảnh báo (QUAN TRỌNG)

Nếu `warnings` chứa cảnh báo liên quan đến **CODEX/WINDOWS** (có chữ "CẢNH BÁO CODEX/WINDOWS" hoặc "context-bleed"):

> **HARD WARN — RỦI RO CONTEXT-BLEED TRÊN WINDOWS:**
> Khi dùng backend Codex trên Windows, codex.CMD từng cắt xén prompt positional arg dài
> khiến Codex mất style anchor và tự bịa cảnh (ảnh ra photorealistic thay vì người que).
> Bản vendored đã có fix (STDIN invocation) nên an toàn để dùng, nhưng **vẫn nên**:
> - Kiểm tra kỹ từng ảnh sau khi pipeline chạy xong.
> - Nếu thấy ảnh sai style, xóa ảnh đó và chạy lại với cùng run-id để gen lại.

Nếu `warnings` có cảnh báo "vendor/videopipe/images.py có thể thiếu fix":
> **BLOCKER TIỀM NĂNG**: vendored images.py không tìm thấy dấu hiệu STDIN fix —
> re-vendor từ `D:/projects/youtube/videopipe/images.py` (bản sau 2026-06-16) trước khi dùng Codex backend.

## Bước 3 — Kết luận

Tóm tắt trạng thái tổng thể: sẵn sàng / chưa sẵn sàng, và bước tiếp theo cụ thể nếu cần.

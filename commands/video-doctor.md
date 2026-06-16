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
- `ffmpeg`, `ffprobe`, `codex`, `edge-tts`, `anti2api` — có (✓) hay thiếu (✗).

### Backend khuyên dùng
Nêu `recommended_backend` ("gemini" hoặc "codex") và giải thích ngắn lý do:
- `gemini`: anti2api server đang chạy + ANTI2API_KEY đã set → chất lượng ảnh cao hơn, portable hơn.
- `codex`: anti2api chưa sẵn sàng → dùng Codex CLI (keyless nhưng cần cẩn thận trên Windows).

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
> Bản vendored đã có fix (STDIN invocation), nhưng **KHUYẾN NGHỊ MẠNH**:
> - Bật anti2api/Gemini backend để tránh rủi ro hoàn toàn.
> - Cài anti2api (cổng 8046 mặc định) rồi set `ANTI2API_BASE_URL` + `ANTI2API_KEY`.
> - Chạy lại `/video-doctor` để xác nhận `recommended_backend` chuyển sang `"gemini"`.

Nếu `warnings` có cảnh báo "vendor/videopipe/images.py có thể thiếu fix":
> **BLOCKER TIỀM NĂNG**: vendored images.py không tìm thấy dấu hiệu STDIN fix —
> re-vendor từ `D:/projects/youtube/videopipe/images.py` (bản sau 2026-06-16) trước khi dùng Codex backend.

Các cảnh báo khác (anti2api chết, key chưa set): hiển thị trực tiếp và đề nghị người dùng xem xét.

## Bước 3 — Kết luận

Tóm tắt trạng thái tổng thể: sẵn sàng / chưa sẵn sàng, và bước tiếp theo cụ thể nếu cần.

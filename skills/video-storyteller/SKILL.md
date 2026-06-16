---
name: video-storyteller
description: Tạo video kể chuyện/giải thích tiếng Anh từ một chủ đề — storyboard do Claude viết, TTS+phụ đề, ảnh AI, ghép ffmpeg. Trigger khi user muốn tạo video YouTube hoặc video giải thích cho bất kỳ chủ đề nào.
---

# Skill: video-storyteller

Claude là **bộ điều phối chính** — tự viết storyboard, kiểm từng bước, gọi công cụ. KHÔNG chạy một script đầu-cuối rời.

---

## Bước 1 — Kiểm tra môi trường

Chạy:
```
python "${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/scripts/check_env.py" --json
```

Parse JSON trả về (`tools`, `recommended_backend`, `blockers`, `warnings`):

- **Nếu `blockers` không rỗng** (thiếu ffmpeg, ffprobe, edge-tts): DỪNG ngay, báo user cách cài từng tool còn thiếu rồi chạy lại `/video-doctor` để xác nhận.
- Lấy `recommended_backend` ("gemini" hoặc "codex") — dùng ở bước 4.
- Nếu `warnings` có "CẢNH BÁO CODEX/WINDOWS" hoặc "context-bleed":
  > **Cảnh báo:** backend Codex trên Windows có rủi ro context-bleed (ảnh ra sai style). Bản vendored đã có fix STDIN, nhưng khuyến nghị bật anti2api/Gemini backend để an toàn hơn (set `ANTI2API_BASE_URL` + `ANTI2API_KEY`, chạy lại `/video-doctor`).

---

## Bước 2 — Làm rõ chủ đề và phong cách

Nếu user chưa cho biết đủ thông tin, hỏi:
1. **Chủ đề** cụ thể (không hỏi nếu đã rõ từ `/create-video <chủ đề>`).
2. **Phong cách** — gợi ý:
   - `stick-figure` (mặc định): whiteboard explainer, người que, giải thích khái niệm.
   - `cinematic`: kể chuyện tối/huyền bí, có nhân vật phức tạp hơn.
   - Xem thêm: `references/styles.md`.

Không hỏi quá 2 câu — nếu chủ đề và phong cách đã đủ từ `/create-video`, đi thẳng bước 3.

---

## Bước 3 — Tự viết storyboard JSON

Viết storyboard theo hướng dẫn tâm lý kể chuyện trong `references/storyboard-craft.md`.

Schema bắt buộc (xem `references/storyboard.schema.json`):
```json
{
  "title": "...",
  "style_anchor": "...",
  "character_sheet_prompt": "...",
  "shots": [
    {
      "id": 0,
      "narration": "1-2 câu lời kể tiếng Anh.",
      "image_prompt": "Mô tả 1 cảnh cụ thể, positive-only (không liệt kê tránh gì).",
      "images": 1
    }
  ]
}
```

Quy tắc viết storyboard:
- Mỗi shot: 1-2 câu narration (≤30 giây TTS).
- `images=2` ở đoạn cao trào để đổi ảnh nhanh tạo nhịp; phần còn lại để 1.
- `image_prompt` phải **positive-only** — KHÔNG liệt kê "Avoid: ...", để style anchor kiểm soát. (Negative prompt khiến gpt-image-2 vẽ đúng các token đó.)
- `character_sheet_prompt` mô tả nhân vật chính đủ rõ để sinh reference image nhất quán.
- Tổng: 8-14 shot (video 2-4 phút), theo cấu trúc Pixar story spine trong `references/storyboard-craft.md`.

Lưu storyboard vào `<cwd>/video-out/<slug-chủ-đề>.json` (cùng nơi với artifact video để dễ quản lý). Tạo thư mục `<cwd>/video-out/` nếu chưa có.

---

## Bước 4 — Chọn backend và gọi pipeline

Backend = `recommended_backend` từ bước 1 (gemini nếu anti2api sống + có key; codex nếu không).

Xác định đường dẫn nhạc nền (tùy chọn):
```
${CLAUDE_PLUGIN_ROOT}/assets/music/lofi_bed.mp3
```

Gọi pipeline (có thể thêm `--run-id <id>` để resume nếu bị dở):
```
python "${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/scripts/run_pipeline.py" \
  --storyboard "<cwd>/video-out/<slug>.json" \
  --style <style> \
  --backend <backend> \
  --music "${CLAUDE_PLUGIN_ROOT}/assets/music/lofi_bed.mp3"
```

Pipeline sẽ in path final.mp4 ra stdout khi hoàn tất.

**Resume-friendly:** nếu pipeline bị dở (mất kết nối, timeout), thêm `--run-id <id-cũ>` để tiếp tục từ chỗ dở (artifact đã gen sẽ được skip).

---

## Bước 5 — Verify ảnh (kiểm bằng mắt)

Sau khi pipeline chạy xong (hoặc trong lúc chạy nếu run dài), đọc các file ảnh:
```
<cwd>/video-out/work/<run-id>/scene_*.png
<cwd>/video-out/work/<run-id>/style_sheet.png
```

Kiểm tra:
- **Đúng chủ đề**: ảnh có liên quan đến narration của shot đó không?
- **Style nhất quán**: tất cả ảnh cùng phong cách (cùng màu sắc, cùng kiểu nhân vật) — không có ảnh nào trông khác hẳn nhóm.
- **Context-bleed**: có ảnh nào ra photorealistic trong khi style là stick-figure không?

Nếu phát hiện ảnh sai (context-bleed, lệch style, không liên quan chủ đề):
1. Xóa ảnh đó: `del "<cwd>/video-out/work/<run-id>/scene_X.png"` (hoặc `scene_X_Y.png`).
2. Chạy lại run_pipeline với cùng `--run-id` — resume sẽ gen lại ảnh còn thiếu, giữ nguyên phần đã xong.
3. Lặp cho đến khi tất cả ảnh đạt.

---

## Bước 6 — Verify desync

Đọc stderr của run_pipeline (hoặc log file nếu có). Tìm dòng có pattern:
```
WARNING videopipe: shot X/N desync (tiếp tục): ...
```

Nếu tìm thấy dòng desync:
> **Cảnh báo:** Phát hiện lệch thời lượng ở shot X — phụ đề có thể lệch khỏi giọng đọc ở đoạn đó. Kiểm tra `seg_X.mp4` bằng cách xem và nghe, so sánh sub với audio. Nếu lệch rõ, xóa `seg_X.mp4` + chạy lại pipeline để tạo lại segment đó.

*(Lưu ý kỹ thuật: desync nhỏ ≤1 frame là codec rounding bình thường — không cần lo. Desync lớn mới cần xử lý.)*

---

## Bước 7 — Báo kết quả

Khi pipeline hoàn tất:
1. Báo path final.mp4: `<cwd>/video-out/work/<run-id>/final.mp4`.
2. Probe thời lượng: `ffprobe -v quiet -show_entries format=duration -of csv=p=0 "<final.mp4>"` rồi in ra cho user.
3. Nhắc user mở file và xem/nghe để verify tổng thể (audio, sub, hình, nhạc nền).

---

## Ghi chú cho Claude (điều phối)

- Pipeline viết artifact vào `<cwd>/video-out/` — KHÔNG vào thư mục plugin.
- `cwd` = thư mục project người dùng đang đứng khi gọi `/create-video` — artifact luôn rơi đúng chỗ đó.
- Không hardcode path tuyệt đối user-specific; dùng `${CLAUDE_PLUGIN_ROOT}` cho mọi ref tới plugin.
- Không log API key (ANTI2API_KEY) dù dưới bất kỳ hình thức nào.

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
- `recommended_backend` luôn = `"codex"` — backend ảnh duy nhất của plugin.
- Nếu `warnings` có "CẢNH BÁO CODEX/WINDOWS" hoặc "context-bleed":
  > **Cảnh báo:** backend Codex trên Windows có rủi ro context-bleed (ảnh ra sai style). Bản vendored đã có fix STDIN — an toàn để dùng. Hãy kiểm tra kỹ từng ảnh sau khi pipeline chạy xong; nếu thấy ảnh sai style, xóa ảnh đó và chạy lại với cùng run-id để gen lại.

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
      "images": 1,
      "mood": "calm"
    }
  ]
}
```

Quy tắc viết storyboard:
- Mỗi shot: 1-2 câu narration (≤30 giây TTS).
- `images=2` ở đoạn cao trào để đổi ảnh nhanh tạo nhịp; phần còn lại để 1.
- `image_prompt` phải **positive-only** — KHÔNG liệt kê "Avoid: ...", để style anchor kiểm soát. (Negative prompt khiến gpt-image-2 vẽ đúng các token đó.)
- `character_sheet_prompt` mô tả nhân vật chính đủ rõ để sinh reference image nhất quán.
- Ngân sách lời và số shot: nếu có `--target-minutes N`, ngân sách từ = `N × wpm × 0.88` (wpm dẫn xuất từ rate TTS, mặc định +5% → ≈157.5 wpm). Số shot ≈ `(N × 60) / 18–22s` mỗi shot. Nếu không có `--target-minutes`, giữ 8–14 shot (video ~2–4 phút). Theo cấu trúc Pixar story spine trong `references/storyboard-craft.md`.
- **VFX hài TIẾT CHẾ** (chỉ khi user bật `--vfx`): gắn beat VFX vào câu chốt, đỉnh hài hước, hoặc điểm nhấn cảm xúc — tối đa ≤2–3 beat/phút toàn video (rule-of-three: dùng nhiều hơn = mất tác dụng). Mỗi shot ≤3 beat. Thời lượng effect 0.3–0.5s. KHÔNG đặt VFX ở mọi shot — để khoảng thở để beat có trọng lượng. Ví dụ tốt: `{"type": "pop", "text": "Wait—", "at": 3.2, "duration": 0.4}` ngay trước câu twist. Xem `references/storyboard.schema.json` field `vfx`.
- **Gán `mood` cho mỗi shot** (tùy chọn nhưng nên có khi bật `music_mode="emotion"`):
  - `calm` — đoạn dẫn nhập, giải thích bình thản, bối cảnh yên tĩnh.
  - `uplifting` — đoạn hi vọng, phục hồi, tương lai tươi sáng.
  - `tense` — đoạn cao trào, khủng hoảng, nguy hiểm, xung đột.
  - `somber` — đoạn buồn, mất mát, hậu quả nặng nề.
  - `playful` — đoạn nhẹ nhàng, hài hước, ví dụ sinh động.
  - `triumphant` — đoạn thắng lợi, thành công, kết thúc mạnh mẽ.
  - Nếu bỏ field `mood`, engine tự suy từ keyword trong narration (kém chính xác hơn).

Lưu storyboard vào `<cwd>/video-out/<slug-chủ-đề>.json` (cùng nơi với artifact video để dễ quản lý). Tạo thư mục `<cwd>/video-out/` nếu chưa có.

---

## Bước 4 — Gọi pipeline

Backend ảnh = codex (mặc định, duy nhất). Không cần chọn backend.

**Chế độ nhạc khuyến nghị — emotion (khi đã có music library):**

Thư mục nhạc theo 6 mood: `${CLAUDE_PLUGIN_ROOT}/assets/music/`
Các mood hiện có: `calm/`, `uplifting/`, `tense/`, `somber/`, `playful/`, `triumphant/`
(Mood chưa có .mp3 có SOURCE.txt hướng dẫn nạp thủ công — xem `assets/music/CREDITS.txt`)

Gọi pipeline với emotion mode (khuyến nghị khi storyboard đã gán `mood` cho từng shot):
```
python "${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/scripts/run_pipeline.py" \
  --storyboard "<cwd>/video-out/<slug>.json" \
  --style <style> \
  --music-library "${CLAUDE_PLUGIN_ROOT}/assets/music" \
  --music-mode emotion
```

Fallback — dùng nhạc nền đơn khi chưa có đủ library:
```
python "${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/scripts/run_pipeline.py" \
  --storyboard "<cwd>/video-out/<slug>.json" \
  --style <style> \
  --music "${CLAUDE_PLUGIN_ROOT}/assets/music/lofi_bed.mp3"
```

Pipeline sẽ in path final.mp4 ra stdout khi hoàn tất.

**Resume-friendly:** nếu pipeline bị dở (mất kết nối, timeout), thêm `--run-id <id-cũ>` để tiếp tục từ chỗ dở (artifact đã gen sẽ được skip).

> **QUAN TRỌNG — ranh giới thay đổi rate:** nếu cấu hình TTS rate thay đổi (ví dụ: từ −4% lên +5%), các file `scene_*.mp3` trong work-dir cũ đã được tổng hợp ở rate cũ và KHÔNG còn hợp lệ. KHÔNG dùng `--run-id` cũ qua ranh giới này — resume sẽ skip audio cũ và giữ nguyên, dẫn đến video trộn nhịp cũ+mới. Khi đổi rate, luôn bắt đầu run mới (không truyền `--run-id`).

---

## Bước 5 — Verify ảnh (kiểm bằng mắt — QUAN TRỌNG với Codex)

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

> **Lưu ý:** Vì backend Codex trên Windows từng có lỗi context-bleed (đã fix bằng STDIN trong bản vendored), hãy luôn kiểm tra ảnh kỹ. Bản vendored đã an toàn nhưng vẫn nên xem xác nhận bằng mắt.

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

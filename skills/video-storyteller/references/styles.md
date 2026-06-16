# Style Presets — video-storyteller

## Preset có sẵn

### `stick-figure` (mặc định cho giải thích)

**Tên nội bộ:** `stick-figure-explainer`

**Style anchor:**
```
simple hand-drawn stick figure cartoon on a clean off-white paper background,
thick black marker outlines, minimal flat doodle style, lots of empty space,
a few simple props and labels drawn as doodles, friendly and clear, 16:9,
whiteboard explainer aesthetic
```

**Khi dùng:**
- Video giải thích khái niệm (tài chính, khoa học, lịch sử, tâm lý học).
- Nội dung cần trực quan hóa quy trình, so sánh, số liệu.
- Muốn nhất quán style cao giữa các shot (người que đơn giản, ít token → ít context-bleed).

**Ví dụ:** `dca_stickman.json` — video DCA người que 13 shot.

---

### `cinematic` (mặc định cho kể chuyện)

**Tên nội bộ:** `mystery-storytelling`

**Style anchor:**
```
cinematic dark moody illustration, muted desaturated palette,
soft volumetric lighting, painterly storybook style, 16:9
```

**Khi dùng:**
- Video kể chuyện có tình tiết (bí ẩn, lịch sử, true crime nhẹ).
- Nhân vật phức tạp hơn, cần cảm xúc rõ trên khuôn mặt.
- Chấp nhận ảnh đa dạng hơn (không cần whiteboard aesthetic).

**Ví dụ:** `signal_from_room_4.json` — câu chuyện bí ẩn.

---

## Thêm preset mới

1. Mở `vendor/videopipe/config.py`.
2. Tạo `StylePreset(name=..., image_style_anchor=..., use_case_slug=...)`.
3. Thêm vào `STYLE_PRESETS` dict với key là tên CLI.
4. Cập nhật file này với mô tả + ví dụ khi nào dùng.
5. Re-vendor (`videopipe/config.py` gốc ở `D:/projects/youtube/videopipe/`) nếu cần đồng bộ.

**Lưu ý `use_case_slug`:** taxonomy slug của Codex imagegen skill — ảnh hưởng tới mô hình con Codex chọn.
Giá trị an toàn: `"scientific-educational"` (stick-figure), `"illustration-story"` (cinematic).

---

## Lưu ý style anchor

- Style anchor được **lặp vào đầu mọi image_prompt** → giữ nhất quán giữa các shot.
- Không cần viết lại style anchor trong `image_prompt` — viết prompt cảnh cụ thể là đủ.
- Nếu storyboard có `style_anchor` field → ghi đè anchor của preset (dùng để override per-video).

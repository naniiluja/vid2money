---
name: grill-video
description: Engine phỏng vấn nội bộ — hỏi người dùng từng câu một để thu thập chi tiết trước khi tạo video (chủ đề, thời lượng, style, VFX, nhạc, đối tượng, outro). CHỈ được gọi bởi skill video-storyteller (Bước 2) hoặc command /create-video — không phải command độc lập, đừng trigger từ hội thoại thường.
user-invocable: false
allowed-tools: Read, Glob, Grep, AskUserQuestion
---

# grill-video — engine phỏng vấn trước khi tạo video

Một skill cha (`video-storyteller`) đã gọi bạn qua Skill tool. Nhiệm vụ: phỏng vấn người dùng **từng câu một** để thu thập đủ chi tiết cho một video chất lượng, rồi trả về một **summary có cấu trúc** để skill cha viết storyboard và gọi pipeline.

Chủ đề người dùng đã cho có thể được nhúng trong câu gọi (vd "chủ đề: …"). Nếu đã rõ, **bỏ qua** câu hỏi chủ đề — đừng hỏi lại cái họ vừa gõ.

## Kỷ luật phỏng vấn (luôn áp dụng)

- **Mỗi lần một câu.** KHÔNG gộp nhiều câu hỏi. Hỏi → chờ trả lời → để câu trả lời đó định hình câu kế.
- **Tự trả lời trước khi hỏi.** Trước mỗi câu, thử tự đáp từ context có sẵn (Read/Glob/Grep `${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/references/styles.md`, `references/storyboard.schema.json`, các storyboard mẫu trong `stories/`). Chỉ hỏi cái không tự suy được; cái suy được thì xác nhận thay vì hỏi mù.
- **Luôn kèm khuyến nghị.** Mỗi câu nêu sẵn câu trả lời đề xuất + lý do một dòng để người dùng chỉ cần xác nhận. Nếu họ defer ("tùy bạn"), proceed theo khuyến nghị.
- **Dùng AskUserQuestion cho câu có lựa chọn rõ** (style/VFX/nhạc/thời lượng — 2–4 option). Câu mở (chủ đề, góc kể, đối tượng, outro) hỏi bằng **text tự do**.
- **Dừng khi đủ.** Không hỏi quá điểm hữu ích. Bỏ qua mọi câu đã rõ từ context.
- **Tổng kết cuối cùng.** Kết thúc bằng block `## Chi tiết đã thu thập` (xem cuối file) — sẵn để skill cha map vào flag.

## Các khía cạnh cần hỏi (theo thứ tự, bỏ qua cái đã rõ)

### (1) Chủ đề + góc kể + thông điệp — *text tự do*
- Chủ đề cụ thể (BỎ QUA nếu đã rõ từ câu gọi/`$ARGUMENTS`).
- Góc kể chuyện / thông điệp chính muốn người xem nhớ (vd "DCA giúp người mới đầu tư bớt sợ biến động").
- Khuyến nghị: nếu chủ đề rộng, đề xuất một góc hẹp + một thông điệp một câu.

### (2) Thời lượng mục tiêu → flag `--target-minutes` — *AskUserQuestion*
- Hỏi video dài bao nhiêu phút. Option gợi ý: ~2–3 phút (ngắn, gọn) / ~4–5 phút / "để mặc định".
- Giải thích ngắn: thời lượng chi phối số shot và ngân sách lời (xem `video-storyteller/SKILL.md` Bước 3 — ngân sách từ = phút × wpm × 0.88; số shot ≈ phút×60 / 18–22s).
- Khuyến nghị: để mặc định (~2–4 phút, 8–14 shot) nếu người dùng không chắc → KHÔNG đặt `--target-minutes`.

### (3) Style + VFX + nhạc — *AskUserQuestion (gộp 1 lượt, nhiều câu hỏi)*
Hỏi gộp trong một lần để interview gọn:
- **Style** → flag `--style`: `stick-figure` (mặc định — whiteboard explainer, người que, hợp giải thích khái niệm) | `cinematic` (kể chuyện tối/huyền bí, nhân vật phức tạp). Tham chiếu `references/styles.md`.
- **VFX hài** → flag `--vfx`: bật/tắt (mặc định TẮT — chỉ bật khi muốn beat hài tiết chế ở câu chốt).
- **Nhạc** → flag `--music-mode`: `emotion` (đổi nhạc theo mood mỗi đoạn — khuyến nghị nếu library đủ) | `static` (1 bed cố định — fallback an toàn).
- Khuyến nghị: `stick-figure` + VFX tắt + `--music-mode static` cho video giải thích chuẩn; gợi `cinematic` nếu là kể chuyện có cốt truyện.

### (4) Đối tượng khán giả + outro — *text tự do*
- Đối tượng khán giả (ảnh hưởng tone narration: người mới / chuyên gia / thiếu nhi…) — KHÔNG cần flag, chỉ định hướng cách viết.
- Chữ end-card → flag `--outro-text` (vd "Subscribe để xem thêm" / tên kênh). Mặc định để trống nếu không cần.
- Khuyến nghị: suy đối tượng từ chủ đề (vd chủ đề tài chính cơ bản → "người mới"); outro để trống trừ khi người dùng có CTA cụ thể.

## Định dạng tổng kết (BẮT BUỘC ở cuối)

Kết thúc bằng block đúng tiêu đề này để skill cha parse:

```
## Chi tiết đã thu thập
- Chủ đề / góc kể / thông điệp: …
- Thời lượng (--target-minutes): … (hoặc "mặc định, không đặt")
- Style (--style): stick-figure | cinematic
- VFX (--vfx): bật | tắt
- Nhạc (--music-mode): static | emotion
- Đối tượng khán giả: … (định hướng tone, không phải flag)
- Outro (--outro-text): … (hoặc "trống")
```

Chỉ liệt kê flag CÓ THẬT ở trên — KHÔNG bịa flag mới. Giọng đọc (voice) do engine cấu hình, KHÔNG có flag ở lớp wrapper nên KHÔNG hỏi.

# Storyboard Craft — Tâm lý kể chuyện cho video giải thích

> Áp dụng khi Claude tự viết storyboard. Ưu tiên: giữ người xem đến cuối > thông tin chính xác.

---

## Nhịp nói và nhấn nhá (không SSML)

**Rate mặc định `+5%` ≈ 157.5 wpm** — nhịp podcast tự nhiên, không lê thê.
Ngân sách từ = `N × 157.5 × 0.88` (hàm `expected_words` dẫn xuất từ rate).

**edge-tts KHÔNG nhận SSML** — `<emphasis>`, `<break>`, `<prosody>` bị strip hoàn toàn.
Nhấn nhá bằng dấu câu và cách viết:

- **Ngừng ngắn**: dấu phẩy `,` hoặc em-dash `—` (ngừng 1-2 beat).
- **Ngừng dài/kịch tính**: dấu chấm lửng `...` (ngừng rõ hơn, dùng ở câu mở hoặc twist).
- **Nhấn từ khoá**: CAPS — viết HOA toàn bộ từ quan trọng nhất trong câu (TIẾT CHẾ — tối đa 1-2 từ/shot, không viết hoa cả câu).
- **Ví dụ tốt**: `"The person who tries to time the market — ALWAYS — ends up poorer."`
- **Ví dụ kém**: `"THE PERSON WHO TRIES TO TIME THE MARKET ALWAYS ENDS UP POORER."` (viết hoa toàn câu = mất hiệu quả nhấn).

---

## Cấu trúc Pixar Story Spine

Khung xương sống bắt buộc cho mọi video. Số shot và ngân sách lời phụ thuộc `--target-minutes`:
- **Có `--target-minutes N`**: ngân sách từ = `N × wpm × 0.88` (wpm ≈ 157.5 với rate +5%). Số shot ≈ `(N × 60) / 18–22s` mỗi shot.
- **Không có `--target-minutes`**: mặc định 8–14 shot (video ~2–4 phút).

Cấu trúc 5 act:

1. **Setup + câu hỏi gây tò mò** (shot 0-1): Mở bằng nghịch lý hoặc câu hỏi "ngược đời" khiến người xem không thể không muốn biết đáp án. Không mở bằng định nghĩa.
2. **Escalation** (shot 2-4): Dẫn dắt vào vấn đề — tại sao nó khó, tại sao người ta thường giải quyết sai.
3. **Giải pháp** (shot 4-7): Cái gì thực sự hoạt động — giải thích cơ chế, không chỉ "hãy làm X".
4. **Twist** (shot 7-9): Cái gì bất ngờ / phản trực giác mà ít ai biết — đây là điểm giữ người xem.
5. **Kết đồng cảm** (shot cuối): Kết nối cảm xúc — người xem nhận ra họ đã/đang làm điều này rồi, hoặc cảm thấy được trao quyền hành động. Không kết bằng lời khuyên sáo rỗng.

---

## Công cụ tâm lý cần dùng

### Curiosity Gap (khoảng tò mò)
Tạo khoảng trống giữa những gì người xem biết và những gì họ muốn biết. Ví dụ:
- Kém: "Hôm nay chúng ta sẽ học về Dollar-Cost Averaging."
- Tốt: "Người đoán đáy thị trường hoàn hảo thường nghèo hơn người không đoán gì cả. Tôi sẽ cho bạn xem tại sao."

### Loss Aversion (sợ mất mát)
Não người phản ứng mạnh hơn với mất mát hơn là lợi ích (2x). Frame vấn đề theo góc "bạn đang mất gì nếu không làm" thay vì "bạn sẽ được gì".

### Pattern Interrupt (phá vỡ kỳ vọng)
Mỗi 2-3 shot, thêm một câu hoặc cảnh làm người xem phải dừng lại: "Nhưng đây là điều không ai nói với bạn..." / "Và đây là nơi mọi thứ trở nên bất ngờ..."

### Social Proof bằng cụ thể
Thay "nghiên cứu cho thấy" bằng tên cụ thể: "Nghiên cứu Vanguard năm 2012 với dữ liệu 10 năm từ 3 thị trường..."

---

## Ví dụ thực tế (từ dca_stickman.json)

| Shot | Kỹ thuật dùng | Narration |
|------|--------------|-----------|
| 0 | Curiosity gap + nghịch lý | "The person who perfectly guesses the bottom of the market is usually poorer than the person who never guesses at all." |
| 2 | Loss aversion | "When prices go up, they feel afraid of overpaying. When prices fall, they feel afraid it will fall more." |
| 6 | Reframe (crash = sale) | "A market crash, the thing everyone fears, actually becomes a discount sale for the disciplined investor." |
| 8 | Pattern interrupt (twist) | "But now here is the twist that almost nobody tells you. Dollar-Cost Averaging usually does not make you the most money." |
| 12 | Kết đồng cảm | "If you put money into a retirement fund from your paycheck, you are already doing it. You have been dollar-cost averaging this whole time." |

---

## Quy tắc viết shot

- **Narration**: 1-2 câu, tối đa ~25 giây TTS. Tiếng Anh, giọng kể chuyện chủ động (không bị động).
- **image_prompt**: Mô tả 1 cảnh trực quan, cụ thể. **Positive-only** — KHÔNG viết "avoid", "no", "without". Style anchor sẽ kiểm soát phong cách.
- `images=2` cho shot twist/cao trào để đổi ảnh nhanh tạo nhịp; phần còn lại để `images=1`.
- Tránh: cảnh trừu tượng ("the concept of..."), cảnh đám đông generic, cảnh không hành động.
- Ưu tiên: nhân vật đang làm gì đó cụ thể + 1-2 prop doodled + biểu cảm rõ.

---

## Cấu trúc shot cho 12-shot video (ví dụ)

```
Shot  0: [Nghịch lý mở đầu]
Shot  1: [Nhân vật + câu hỏi chưa trả lời]
Shot  2: [Vấn đề 1 — khi giá lên]
Shot  3: [Vấn đề 2 — khi giá xuống / vòng lặp]
Shot  4: [Tên tâm lý học cho vấn đề]
Shot  5: [Giải pháp — cơ chế cụ thể]
Shot  6: [Cái gì xảy ra — cơ chế tự nhiên]
Shot  7: [Reframe: vấn đề trở thành cơ hội, images=2]
Shot  8: [Twist — điều phản trực giác]
Shot  9: [Bằng chứng cụ thể cho twist, images=2]
Shot 10: [Tại sao vẫn làm — giá trị thật sự]
Shot 11: [Tóm lại — một dòng cốt lõi]
Shot 12: [Kết đồng cảm — bạn đã làm rồi / call to not-stop]
```

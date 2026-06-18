---
description: Tạo video kể chuyện/giải thích tiếng Anh từ một chủ đề. Dùng: /create-video <chủ đề>.
---

# /create-video

Nạp skill `video-storyteller` và tạo video cho chủ đề: **$ARGUMENTS**

Thực hiện toàn bộ quy trình trong `${CLAUDE_PLUGIN_ROOT}/skills/video-storyteller/SKILL.md`:
kiểm tra môi trường → phỏng vấn chi tiết qua grill-video → tự viết storyboard → gọi pipeline → verify ảnh → báo kết quả.

Artifact video xuất ra `<thư mục hiện tại>/video-out/`.

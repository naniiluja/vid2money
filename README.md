# video-storyteller — Plugin Claude Code tạo video kể chuyện

Plugin tự động biến một **chủ đề bất kỳ** thành video giải thích/kể chuyện tiếng Anh hoàn chỉnh:
`storyboard → TTS → ảnh AI → ghép ffmpeg → final.mp4 1080p`.

**Claude là bộ điều phối chính** — tự viết storyboard (cấu trúc Pixar story spine), kiểm từng ảnh bằng mắt, gen lại nếu chưa đạt, rồi lắp ráp video. Không chạy một script đầu-cuối rời.

Output: `<thư_mục_dự_án>/video-out/work/<run-id>/final.mp4` — video 1080p h264/yuv420p, intro/outro fade, phụ đề burn-in, nhạc nền lofi.

Repo: `naniiluja/vid2money` (private). Cài 1 lần, dùng được ở **bất kỳ** project Claude Code nào.

---

## Yêu cầu (phụ thuộc)

Plugin **KHÔNG tự cài** bất kỳ dependency nào. Chạy `/video-doctor` để biết còn thiếu gì.

### Bắt buộc

| Công cụ | Kiểm tra | Cài đặt |
|---------|----------|---------|
| **ffmpeg + ffprobe** | `ffmpeg -version` | [ffmpeg.org/download.html](https://ffmpeg.org/download.html) — build có `libass` (filter `subtitles`/`zoompan`) |
| **Python 3.11+** | `python --version` | [python.org](https://www.python.org/downloads/) |
| **edge-tts** | `python -c "import edge_tts"` | `pip install edge-tts>=6.1.0` — cần internet khi gen audio |

### Backend ảnh (cần ít nhất 1)

| Backend | Cần gì | Chất lượng | Khi nào nên dùng |
|---------|--------|-----------|-----------------|
| **Codex CLI** (mặc định, keyless) | Login ChatGPT Plus; `codex` trong PATH | Trung bình | Không có anti2api; thử nhanh |
| **anti2api / Gemini** (khuyên dùng) | Server local port 8046; `ANTI2API_BASE_URL` + `ANTI2API_KEY` set | Cao hơn, nhất quán nhân vật | Production; tránh context-bleed Windows |

> **Lưu ý Codex trên Windows:** `codex.CMD` từng cắt xén prompt dài → ảnh ra sai style (context-bleed). Bản vendored đã có fix STDIN, nhưng **khuyến nghị** dùng anti2api/Gemini để an toàn hơn.

---

## Cài đặt

Cài 1 lần — sau đó dùng được ở mọi project.

### 1. Thêm marketplace

**Cách A — từ GitHub (khuyên dùng):**

```
/plugin marketplace add https://github.com/naniiluja/vid2money.git
```

> ⚠️ Repo là **private** + Claude Code clone qua git. Dùng **URL HTTPS đầy đủ** (`.git`) như trên để git xác thực qua credential HTTPS đã lưu (vd qua `gh auth`). KHÔNG dùng dạng rút gọn `naniiluja/vid2money` — nó mặc định thử SSH (`git@github.com`) và sẽ lỗi `Permission denied (publickey)` nếu chưa cấu hình SSH key.

**Cách B — từ thư mục local (dành cho dev/sửa plugin):**

```
/plugin marketplace add D:/projects/video-storyteller
```

### 2. Cài plugin

```
/plugin install video-storyteller@video-storyteller-market
```

### 3. Xác nhận cài thành công

Sau khi cài, gõ `/video-doctor` ở bất kỳ project nào — Claude sẽ chẩn đoán môi trường và báo sẵn sàng hay chưa.

---

## Cách dùng

### Bước 1 — Chẩn đoán môi trường

```
/video-doctor
```

Claude sẽ kiểm tra ffmpeg, ffprobe, edge-tts, Codex, anti2api rồi báo cáo:
- Công cụ nào có / thiếu
- Backend khuyên dùng (gemini hay codex)
- Blocker cần xử lý trước khi tạo video

### Bước 2 — Tạo video

```
/create-video <chủ đề>
```

Ví dụ:
```
/create-video How compound interest silently makes you rich
/create-video Why cats always land on their feet
/create-video The day the stock market crashed in 1929
```

**Claude sẽ tự động:**
1. Viết storyboard JSON (8-14 cảnh, cấu trúc Pixar story spine) — lưu vào `<cwd>/video-out/<slug>.json`
2. Chọn backend ảnh (gemini nếu anti2api sống + có key, ngược lại dùng codex)
3. Gọi pipeline: TTS → sinh ảnh → ghép segment → assemble final.mp4
4. Kiểm từng ảnh bằng mắt (style nhất quán? đúng chủ đề? context-bleed?), gen lại nếu cần
5. Báo cáo path final.mp4 + thời lượng

### Artifact đầu ra

```
<cwd>/video-out/
  <slug>.json                    ← storyboard Claude viết
  work/<run-id>/
    final.mp4                    ← video hoàn chỉnh 1080p
    scene_*.mp3 / *.srt          ← audio + phụ đề từng cảnh
    scene_*.png                  ← ảnh từng cảnh
    seg_*.mp4                    ← segment từng cảnh (trước khi assemble)
```

### Resume (tiếp tục dở dang)

Nếu pipeline bị ngắt giữa chừng (mất mạng, timeout), gọi lại với cùng run-id:

```
/create-video <chủ đề>
```

*(Claude nhớ run-id từ session; hoặc chỉ định thủ công trong SKILL.md `--run-id <id-cũ>`.)*

Artifact đã tạo sẽ được giữ nguyên — pipeline tự skip phần đã xong.

---

## Cài đặt backend Gemini (anti2api)

Để dùng backend Gemini chất lượng cao:

**1. Chạy server anti2api (cổng 8046 mặc định):**
```bash
cd D:\projects\anti2api
npm start
```

**2. Set biến môi trường** (KHÔNG hardcode vào code):
```bash
# Windows PowerShell
$env:ANTI2API_BASE_URL = "http://localhost:8046"
$env:ANTI2API_KEY = "<key-từ-file-.env>"

# Hoặc thêm vào ~/.claude/settings.json > env
```

> API key nằm trong `D:\projects\anti2api\.env` — **KHÔNG commit file này**.

**3. Xác nhận:**
```
/video-doctor
```
→ `recommended_backend: "gemini"` = sẵn sàng.

---

## Cấu trúc plugin

```
video-storyteller/
├── .claude-plugin/
│   ├── plugin.json          ← khai báo plugin (name, version, repo)
│   └── marketplace.json     ← khai báo marketplace local
├── commands/
│   ├── video-doctor.md      ← lệnh /video-doctor (chẩn đoán)
│   └── create-video.md      ← lệnh /create-video <chủ đề>
├── skills/video-storyteller/
│   ├── SKILL.md             ← não điều phối: Claude đọc để biết cách chạy
│   ├── scripts/
│   │   ├── check_env.py     ← probe môi trường → JSON
│   │   └── run_pipeline.py  ← wrapper: set env → gọi vendor videopipe
│   └── references/
│       ├── storyboard-craft.md      ← hướng dẫn viết storyboard (Pixar spine)
│       ├── storyboard.schema.json   ← schema JSON storyboard
│       └── styles.md                ← danh sách style preset
├── vendor/videopipe/        ← COPY điểm-thời-gian từ D:/projects/youtube/videopipe
│   ├── config.py            ← đọc VIDEOPIPE_WORK_ROOT / VIDEOPIPE_ASSETS_ROOT (env)
│   ├── pipeline.py          ← orchestrator: run_storyboard()
│   ├── images.py            ← gen ảnh (codex/gemini); có fix STDIN context-bleed
│   ├── tts.py               ← edge-tts → mp3 + SRT
│   ├── ffmpeg_ops.py        ← Ken Burns + assemble + nhạc nền
│   └── ...                  ← (8 module khác)
├── assets/music/
│   ├── lofi_bed.mp3         ← nhạc nền mặc định
│   └── CREDITS.txt          ← attribution nhạc
├── stories/                 ← storyboard mẫu tham khảo
├── tests/                   ← 19 unit test (pytest)
├── requirements.txt         ← edge-tts>=6.1.0
└── .gitignore
```

---

## Re-vendor (cập nhật pipeline khi videopipe gốc thay đổi)

`vendor/videopipe/` là **bản sao điểm-thời-gian** — KHÔNG tự sync với repo gốc.

Khi `D:/projects/youtube/videopipe/` có thay đổi quan trọng (bug fix, tính năng mới), thực hiện:

**1. Copy đè 11 module (và script_schema.json):**
```powershell
# Chạy từ D:/projects/video-storyteller/
$src = "D:\projects\youtube\videopipe"
$dst = "D:\projects\video-storyteller\vendor\videopipe"
Copy-Item "$src\*.py"          $dst -Force
Copy-Item "$src\script_schema.json" $dst -Force
```

**2. Chạy lại test để đảm bảo không hỏng:**
```
python -m pytest tests/ -q
```
Phải xanh hoàn toàn (hiện 19 test).

**3. Bump version trong `.claude-plugin/plugin.json`:**
```json
{ "version": "0.1.1" }
```

**4. Ghi chú lý do re-vendor trong commit message:**
```
chore: re-vendor videopipe 2026-XX-XX — fix <mô tả ngắn>
```

> **Lưu ý:** Sau khi re-vendor, chạy `/video-doctor` để xác nhận `vendor/videopipe/images.py` vẫn có STDIN fix (check_env.py tự kiểm dấu hiệu này).

---

## Khắc phục sự cố

### ffmpeg không tìm thấy
```
BLOCKER: ffmpeg không tìm thấy trong PATH
```
→ Tải từ [ffmpeg.org/download.html](https://ffmpeg.org/download.html), giải nén, thêm thư mục `bin/` vào PATH. Khởi động lại terminal. Build phải có `libass` (kiểm: `ffmpeg -filters | findstr subtitles`).

### edge-tts lỗi mạng
```
RuntimeError: edge-tts failed
```
→ Kiểm tra kết nối internet. edge-tts cần gọi API Microsoft online. Thử lại sau ít phút. Pipeline resume được — không mất artifact đã gen.

### Ảnh ra sai style (context-bleed Codex trên Windows)
```
Triệu chứng: ảnh ra photorealistic dù style là stick-figure
```
→ Bật anti2api/Gemini backend: chạy server anti2api, set `ANTI2API_BASE_URL` + `ANTI2API_KEY`, gọi `/video-doctor` để xác nhận `recommended_backend: "gemini"`.
Nếu vẫn cần dùng Codex: xác nhận `vendor/videopipe/images.py` có STDIN fix (dấu hiệu: `input=stdin_data` + `"-"` trong code).

### Phụ đề lệch giọng đọc (desync)
```
WARNING videopipe: shot X/N desync (tiếp tục): ...
```
→ Desync nhỏ (≤1 frame) là codec rounding bình thường — bỏ qua. Desync lớn: xóa `seg_X.mp4` rồi gọi lại `/create-video` với cùng run-id để gen lại segment đó.

### anti2api server không phản hồi
```
WARNING: anti2api server không phản hồi tại http://localhost:8046
```
→ Chạy server: `cd D:\projects\anti2api && npm start`. Xác nhận cổng 8046 không bị chặn firewall. Kiểm tra `ANTI2API_KEY` đã set chưa.

---

## License

MIT — xem `plugin.json` để biết thêm.

"""Cấu hình pipeline — dataclass thuần, không side-effect ngoài resolve path.

PipelineConfig gom mọi tham số một lần chạy (run) và các đường dẫn artifact
dưới work/<run-id>/. Các bước sau chỉ đọc config + đẩy/nhận artifact qua path
trong đây, nên interface giữa các bước luôn là filesystem + dataclass.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BASE_WPM: float = 150.0


def words_per_minute(rate: str) -> float:
    """Dẫn xuất tốc độ lời thoại (wpm) từ rate TTS edge-tts.

    rate định dạng "+5%", "-4%", "0%", "+0%" → float wpm.
    Raise ValueError nếu format không hợp lệ.
    """
    cleaned = rate.strip()
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", cleaned)
    if m is None:
        raise ValueError(f"rate không hợp lệ: '{rate}'. Định dạng chuẩn: '+5%', '-4%', '0%'.")
    pct = float(m.group(1))
    return BASE_WPM * (1 + pct / 100)


def expected_words(minutes: float, rate: str) -> int:
    """Ngân sách từ cho một video dài `minutes` phút với rate TTS.

    Công thức: round(minutes × wpm × 0.88).
    Hệ số 0.88 dự phòng ngừng nghỉ tự nhiên + phần storyboard không phải narration.
    """
    wpm = words_per_minute(rate)
    return round(minutes * wpm * 0.88)


def is_duration_off(actual_s: float, target_s: float, tol: float = 0.10) -> bool:
    """Trả True nếu actual_s lệch khỏi target_s vượt ngưỡng tol (mặc định 10%).

    Dùng để cảnh báo sau assemble. Không raise — lệch target là warning, không lỗi.
    """
    if target_s <= 0:
        return False
    ratio = actual_s / target_s
    return ratio < (1 - tol) or ratio > (1 + tol)

# Thư mục gốc dự án = cha của package videopipe.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORK_ROOT = PROJECT_ROOT / "work"
ASSETS_ROOT = PROJECT_ROOT / "assets"


def _work_root() -> Path:
    """Trả thư mục work root, đọc env tại thời điểm truy cập (không phải lúc import).

    ROOT CAUSE import-timing: nếu đọc VIDEOPIPE_WORK_ROOT một lần lúc import,
    run_pipeline.py (Task 203) sẽ set env SAU KHI module đã nạp → path bleed
    sang thư mục plugin thay vì thư mục project người dùng.
    Giải pháp: đọc os.environ MỖI LẦN property work_dir/fonts_dir được truy cập.
    """
    raw = os.environ.get("VIDEOPIPE_WORK_ROOT", "").strip()
    if raw:
        return Path(raw)
    return WORK_ROOT


def _assets_root() -> Path:
    """Trả thư mục assets root, đọc env tại thời điểm truy cập (không phải lúc import).

    Cùng lý do import-timing với _work_root() — xem comment trên.
    """
    raw = os.environ.get("VIDEOPIPE_ASSETS_ROOT", "").strip()
    if raw:
        return Path(raw)
    return ASSETS_ROOT


@dataclass(frozen=True)
class StylePreset:
    """Phong cách hình ảnh nhất quán cho cả video (dùng ở bước gen ảnh)."""

    name: str = "mystery-storytelling"
    # Anchor lặp vào mọi image prompt để giữ style/nhân vật nhất quán giữa các scene.
    image_style_anchor: str = (
        "cinematic dark moody illustration, muted desaturated palette, "
        "soft volumetric lighting, painterly storybook style, 16:9"
    )
    use_case_slug: str = "illustration-story"  # taxonomy slug của skill imagegen


# Preset người que (stick-figure) cho video giải thích — nét tối giản, dễ nhất quán.
STICK_FIGURE_STYLE = StylePreset(
    name="stick-figure-explainer",
    image_style_anchor=(
        "simple hand-drawn stick figure cartoon on a clean off-white paper background, "
        "thick black marker outlines, minimal flat doodle style, lots of empty space, "
        "a few simple props and labels drawn as doodles, friendly and clear, 16:9, "
        "whiteboard explainer aesthetic"
    ),
    use_case_slug="scientific-educational",
)


# Registry preset: ánh xạ tên CLI → StylePreset đã định nghĩa sẵn.
# Thêm preset mới: bổ sung entry vào đây, CLI tự nhận choices mới.
STYLE_PRESETS: dict[str, StylePreset] = {
    "cinematic": StylePreset(),           # preset mặc định mystery-storytelling
    "stick-figure": STICK_FIGURE_STYLE,   # video người que / whiteboard explainer
}


def get_style_preset(name: str) -> StylePreset:
    """Tra cứu StylePreset theo tên CLI. Raise ValueError nếu không tìm thấy.

    Tên hợp lệ liệt kê trong STYLE_PRESETS; thêm preset mới ở đó.
    """
    if name in STYLE_PRESETS:
        return STYLE_PRESETS[name]
    valid = ", ".join(sorted(STYLE_PRESETS.keys()))
    raise ValueError(f"Preset '{name}' không tồn tại. Tên hợp lệ: {valid}")


def _slugify(text: str) -> str:
    """Chuẩn hóa chuỗi thành slug an toàn cho tên thư mục."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:40] or "topic"


@dataclass
class PipelineConfig:
    """Toàn bộ tham số + đường dẫn cho một lần chạy pipeline."""

    topic: str
    run_id: str = ""
    image_backend: str = "codex"
    # TTS: giọng tiếng Anh (edge-tts). rate dương = nhanh hơn.
    # Andrew (giọng thế hệ mới, ấm, ngữ điệu phong phú) + +5% ≈ 157.5 wpm — ngân sách
    # từ dẫn xuất qua words_per_minute(rate); nguồn: task-003-tts-pacing.md.
    voice: str = "en-US-AndrewMultilingualNeural"
    tts_rate: str = "+5%"
    # Video.
    fps: int = 30
    width: int = 1920
    height: int = 1080
    style: StylePreset = field(default_factory=StylePreset)
    # Ngân sách thời lượng (tùy chọn): N phút → pipeline cảnh báo nếu actual lệch >10%.
    target_minutes: float | None = None
    # Nhạc nền (tùy chọn): đường dẫn file mp3 + mức giảm âm so với giọng (dB).
    # 16-18 dB là sweet spot (WCAG yêu cầu nền thấp hơn giọng >=20 dB là chuẩn an toàn).
    music_path: Path | None = None
    music_duck_db: float = 16.0
    # Chế độ nhạc nền: "static" = 1 track cố định (hành vi cũ); "emotion" = đổi track theo mood.
    # music_library: thư mục chứa track nhạc emotion (cần khi music_mode="emotion").
    music_mode: str = "static"
    music_library: Path | None = None
    # Intro/outro card — khoảng thở đầu/cuối video.
    # show_title_card=False → bỏ card nhưng giữ hành vi cũ (không có offset SRT).
    intro_seconds: float = 2.0
    outro_seconds: float = 2.5
    show_title_card: bool = True
    outro_text: str = ""  # rỗng = chỉ nền + fade-out, không vẽ chữ

    def __post_init__(self) -> None:
        if not self.run_id:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.run_id = f"{stamp}-{_slugify(self.topic)}"

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def work_dir(self) -> Path:
        """Thư mục artifact cho run này: work/<run-id>/.

        Đọc _work_root() tại thời điểm truy cập để hỗ trợ env override sau import
        (import-timing seam — xem _work_root()).
        """
        return _work_root() / self.run_id

    @property
    def fonts_dir(self) -> Path:
        """Thư mục font: <assets_root>/fonts/.

        Đọc _assets_root() tại thời điểm truy cập — cùng lý do với work_dir.
        """
        return _assets_root() / "fonts"

    @property
    def script_path(self) -> Path:
        return self.work_dir / "script.json"

    @property
    def final_path(self) -> Path:
        return self.work_dir / "final.mp4"

    def scene_audio(self, idx: int) -> Path:
        return self.work_dir / f"scene_{idx}.mp3"

    def scene_srt(self, idx: int) -> Path:
        return self.work_dir / f"scene_{idx}.srt"

    def scene_image(self, idx: int) -> Path:
        return self.work_dir / f"scene_{idx}.png"

    def scene_segment(self, idx: int) -> Path:
        return self.work_dir / f"seg_{idx}.mp4"

    def shot_image(self, idx: int, k: int) -> Path:
        """Ảnh thứ k của shot idx (cho shot nhiều ảnh). k=0 trùng scene_image."""
        if k == 0:
            return self.scene_image(idx)
        return self.work_dir / f"scene_{idx}_{k}.png"

    def ensure_dirs(self) -> None:
        """Tạo thư mục work cho run (idempotent)."""
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def describe(self) -> str:
        """Mô tả config đã resolve (để in ra CLI)."""
        music_info = str(self.music_path) if self.music_path else "(không có)"
        target_info = (
            f"{self.target_minutes} phút "
            f"(≈{expected_words(self.target_minutes, self.tts_rate)} từ)"
            if self.target_minutes is not None
            else "(không đặt)"
        )
        return (
            f"PipelineConfig\n"
            f"  topic      : {self.topic}\n"
            f"  run_id     : {self.run_id}\n"
            f"  voice      : {self.voice} (rate {self.tts_rate})\n"
            f"  resolution : {self.resolution} @ {self.fps}fps\n"
            f"  style      : {self.style.name} [{self.style.use_case_slug}]\n"
            f"  music      : {music_info} (duck {self.music_duck_db} dB)\n"
            f"  target     : {target_info}\n"
            f"  work_dir   : {self.work_dir}\n"
            f"  final      : {self.final_path}"
        )

"""Unit + integration test cho VFX engine — build_vfx_filters + apply qua ffmpeg_ops.

Unit (không cần ffmpeg):
  (a) enabled=False → ""
  (b) mọi effect chứa enable='between(t,
  (c) zoompan dùng d=1
  (d) annotation có setpts → raise ValueError
  (e) cap ≤3 beat/shot

Integration (duration-preserving):
  Segment có-vfx vs không-vfx → ffprobe duration chênh ≤ 1/fps.
  Bọc skipif thiếu ffmpeg — KHÔNG skip âm thầm (in lý do).
"""

from __future__ import annotations

import shutil
import struct
import zlib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# sys.path — vendor videopipe
# ---------------------------------------------------------------------------

import sys

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _PLUGIN_ROOT / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from videopipe.vfx import build_vfx_filters  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture PNG nhỏ hợp lệ (1×1 pixel, trắng) — không dùng PIL, không cần file thật
# ---------------------------------------------------------------------------

def _make_minimal_png(path: Path) -> Path:
    """Tạo PNG 1×1 pixel trắng tối thiểu hợp lệ — không cần Pillow."""
    # PNG header
    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(name: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        body = name + data
        crc = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return length + body + crc

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    # 1 scanline: filter_type=0 + 3 bytes RGB (white)
    raw_row = b"\x00\xFF\xFF\xFF"
    compressed = zlib.compress(raw_row)
    idat_data = compressed

    png = signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", idat_data) + chunk(b"IEND", b"")
    path.write_bytes(png)
    return path


# ---------------------------------------------------------------------------
# CA (a): enabled=False → ""
# ---------------------------------------------------------------------------

class TestBuildVfxFiltersDisabled:
    def test_disabled_returns_empty(self):
        """build_vfx_filters(annotations, enabled=False) → '' (passthrough)."""
        annotations = [
            {"type": "pop", "text": "Wow!", "at": 2.0}
        ]
        result = build_vfx_filters(annotations, enabled=False)
        assert result == ""

    def test_empty_annotations_enabled_returns_empty(self):
        """Không có annotation nào → '' dù enabled=True."""
        result = build_vfx_filters([], enabled=True)
        assert result == ""


# ---------------------------------------------------------------------------
# CA (b): mọi effect chứa enable='between(t,
# ---------------------------------------------------------------------------

class TestBuildVfxFiltersEnableBetween:
    def test_pop_contains_enable_between(self):
        """Effect pop phải chứa enable='between(t,a,b)'."""
        annotations = [{"type": "pop", "text": "Ha!", "at": 1.0, "duration": 0.4}]
        result = build_vfx_filters(annotations, enabled=True)
        assert "enable='between(t," in result

    def test_punch_contains_enable_between(self):
        """Effect punch phải chứa enable='between(t,a,b)'."""
        annotations = [{"type": "punch", "at": 2.0, "duration": 0.3}]
        result = build_vfx_filters(annotations, enabled=True)
        assert "enable='between(t," in result

    def test_shake_contains_enable_between(self):
        """Effect shake phải chứa enable='between(t,a,b)'."""
        annotations = [{"type": "shake", "at": 3.0, "duration": 0.5}]
        result = build_vfx_filters(annotations, enabled=True)
        assert "enable='between(t," in result

    def test_multiple_annotations_all_have_enable_between(self):
        """Nhiều annotation — TẤT CẢ filter phải chứa enable='between(t,'."""
        annotations = [
            {"type": "pop", "text": "Yes!", "at": 1.0, "duration": 0.4},
            {"type": "punch", "at": 2.0, "duration": 0.3},
            {"type": "shake", "at": 3.0, "duration": 0.5},
        ]
        result = build_vfx_filters(annotations, enabled=True)
        # Mỗi filter riêng biệt (phân tách bằng ,) phải có enable=
        # Chúng ta chỉ kiểm tra string tổng thể chứa đủ số lần enable=
        count = result.count("enable='between(t,")
        assert count >= len(annotations)


# ---------------------------------------------------------------------------
# CA (c): zoompan dùng d=1
# ---------------------------------------------------------------------------

class TestBuildVfxFiltersZoompanD1:
    def test_punch_zoompan_d1(self):
        """Effect punch (zoompan) phải dùng d=1 (không thay đổi frame count)."""
        annotations = [{"type": "punch", "at": 2.0, "duration": 0.3}]
        result = build_vfx_filters(annotations, enabled=True)
        assert "zoompan" in result
        assert "d=1" in result

    def test_punch_zoompan_not_d_greater_than_1(self):
        """zoompan d phải đúng là 1, không phải giá trị lớn hơn (đổi frame count)."""
        annotations = [{"type": "punch", "at": 2.0, "duration": 0.3}]
        result = build_vfx_filters(annotations, enabled=True)
        # d=1 phải có, d=2 (hoặc giá trị khác) không được có
        assert "d=1" in result
        assert "d=2" not in result
        assert "d=30" not in result


# ---------------------------------------------------------------------------
# CA (d): annotation có setpts → raise ValueError
# ---------------------------------------------------------------------------

class TestBuildVfxFiltersSetptsGuard:
    def test_setpts_in_annotation_raises(self):
        """Annotation có payload chứa 'setpts' → raise ValueError (guard duration)."""
        annotations = [
            {"type": "pop", "text": "setpts=2.0*PTS", "at": 1.0, "duration": 0.4}
        ]
        with pytest.raises(ValueError, match="setpts"):
            build_vfx_filters(annotations, enabled=True)

    def test_setpts_in_type_field_raises(self):
        """type field chứa 'setpts' → raise ValueError."""
        annotations = [
            {"type": "setpts", "at": 1.0, "duration": 0.3}
        ]
        with pytest.raises(ValueError, match="setpts"):
            build_vfx_filters(annotations, enabled=True)

    def test_setpts_case_insensitive_raises(self):
        """'SETPTS' (uppercase) cũng phải raise ValueError."""
        annotations = [
            {"type": "pop", "text": "SETPTS trick", "at": 1.0, "duration": 0.4}
        ]
        with pytest.raises(ValueError, match="(?i)setpts"):
            build_vfx_filters(annotations, enabled=True)

    def test_clean_annotation_no_raise(self):
        """Annotation bình thường không chứa setpts → không raise."""
        annotations = [{"type": "pop", "text": "Clean!", "at": 1.0, "duration": 0.4}]
        result = build_vfx_filters(annotations, enabled=True)
        assert result != ""


# ---------------------------------------------------------------------------
# CA (e): cap ≤3 beat/shot
# ---------------------------------------------------------------------------

class TestBuildVfxFiltersBeatCap:
    def test_four_annotations_capped_to_three(self):
        """4 annotation → chỉ lấy tối đa 3 (cap beat/shot)."""
        annotations = [
            {"type": "pop", "text": f"Beat {i}", "at": float(i), "duration": 0.3}
            for i in range(4)
        ]
        result = build_vfx_filters(annotations, enabled=True)
        count = result.count("enable='between(t,")
        assert count <= 3

    def test_three_annotations_all_kept(self):
        """3 annotation → giữ cả 3 (đúng ngưỡng cap)."""
        annotations = [
            {"type": "pop", "text": f"Beat {i}", "at": float(i), "duration": 0.3}
            for i in range(3)
        ]
        result = build_vfx_filters(annotations, enabled=True)
        count = result.count("enable='between(t,")
        assert count == 3

    def test_two_annotations_all_kept(self):
        """2 annotation → giữ cả 2."""
        annotations = [
            {"type": "punch", "at": 1.0, "duration": 0.3},
            {"type": "shake", "at": 2.0, "duration": 0.4},
        ]
        result = build_vfx_filters(annotations, enabled=True)
        count = result.count("enable='between(t,")
        assert count == 2

    def test_ten_annotations_capped_to_three(self):
        """10 annotation → chỉ 3 được giữ."""
        annotations = [
            {"type": "pop", "text": f"Beat {i}", "at": float(i), "duration": 0.2}
            for i in range(10)
        ]
        result = build_vfx_filters(annotations, enabled=True)
        count = result.count("enable='between(t,")
        assert count <= 3


# ---------------------------------------------------------------------------
# Integration: duration-preserving (skipif thiếu ffmpeg)
# ---------------------------------------------------------------------------

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

_SKIP_REASON = (
    "ffmpeg/ffprobe không có trong PATH — "
    "integration duration-preserving test bị skip. "
    "Chạy lại trên môi trường có ffmpeg để verify thực tế."
)


@pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason=_SKIP_REASON)
class TestVfxDurationPreserving:
    """Segment có-vfx vs không-vfx → ffprobe duration chênh ≤ 1/fps."""

    def test_segment_duration_preserved_with_vfx(self, tmp_path: Path):
        """make_segment_with_vfx vs make_segment → duration chênh ≤ 1/30s."""
        from videopipe.ffmpeg_ops import make_segment, probe_duration

        img = _make_minimal_png(tmp_path / "test.png")
        audio_dur = 3.0
        fps = 30

        seg_plain = tmp_path / "seg_plain.mp4"
        seg_vfx = tmp_path / "seg_vfx.mp4"

        annotations = [{"type": "pop", "text": "Hi!", "at": 1.0, "duration": 0.4}]

        make_segment(img, audio_dur, seg_plain, fps, width=320, height=180)
        make_segment(
            img, audio_dur, seg_vfx, fps, width=320, height=180,
            vfx_annotations=annotations, vfx_enabled=True,
        )

        dur_plain = probe_duration(seg_plain)
        dur_vfx = probe_duration(seg_vfx)

        tol = 1.0 / fps
        diff = abs(dur_plain - dur_vfx)
        assert diff <= tol, (
            f"VFX đổi duration: plain={dur_plain:.4f}s vfx={dur_vfx:.4f}s "
            f"diff={diff:.4f}s > tol={tol:.4f}s"
        )

"""Tests cho task 007 — bundle sticker doodle VFX.

Bao gồm:
  - unit: thư mục assets/vfx/ tồn tại
  - unit: có ít nhất 1 .png HOẶC SOURCE.txt (phản ánh trạng thái thực)
  - unit: mỗi .png tồn tại có size > 0
  - unit: CREDITS.txt tồn tại (ghi nguồn)
  - unit: SOURCE.txt (nếu có, khi không có .png) không rỗng — phải có link và hướng dẫn
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VFX_ROOT = _REPO_ROOT / "assets" / "vfx"
_CREDITS_PATH = _VFX_ROOT / "CREDITS.txt"
_SOURCE_PATH = _VFX_ROOT / "SOURCE.txt"


class TestVfxAssetsDirectory:
    """Thư mục assets/vfx/ phải tồn tại."""

    def test_vfx_dir_exists(self):
        """assets/vfx/ phải tồn tại."""
        assert _VFX_ROOT.is_dir(), "assets/vfx/ chưa tồn tại"


class TestVfxAssetsContent:
    """Phải có ít nhất 1 .png hoặc SOURCE.txt."""

    def test_has_png_or_source_txt(self):
        """assets/vfx/ phải có ≥1 .png (sticker đã nạp) hoặc SOURCE.txt (bị chặn)."""
        has_png = any(_VFX_ROOT.glob("*.png"))
        has_source = _SOURCE_PATH.exists()
        assert has_png or has_source, (
            "assets/vfx/ không có .png nào và không có SOURCE.txt — "
            "phải có ít nhất một trong hai"
        )

    def test_png_files_are_non_empty(self):
        """Mỗi .png tồn tại phải có size > 0 (không phải file rỗng)."""
        for png in _VFX_ROOT.glob("*.png"):
            assert png.stat().st_size > 0, f"{png.name}: file rỗng (size=0)"

    def test_source_txt_has_content_when_no_png(self):
        """SOURCE.txt (nếu có mà không có .png) phải ghi link + hướng dẫn."""
        has_png = any(_VFX_ROOT.glob("*.png"))
        if _SOURCE_PATH.exists() and not has_png:
            content = _SOURCE_PATH.read_text(encoding="utf-8").strip()
            assert content, "SOURCE.txt rỗng — phải ghi link Pixabay + hướng dẫn drop file"


class TestVfxCredits:
    """CREDITS.txt phải tồn tại."""

    def test_credits_exists(self):
        """assets/vfx/CREDITS.txt phải tồn tại."""
        assert _CREDITS_PATH.exists(), "assets/vfx/CREDITS.txt chưa tồn tại"

    def test_credits_not_empty(self):
        """CREDITS.txt phải có nội dung."""
        if _CREDITS_PATH.exists():
            content = _CREDITS_PATH.read_text(encoding="utf-8").strip()
            assert content, "CREDITS.txt rỗng"

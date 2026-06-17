"""Tests cho task 005 — bundle nhạc theo 6 mood + CREDITS.

Bao gồm:
  - unit: mỗi mood trong MOOD_TAXONOMY có thư mục assets/music/<mood>/
  - unit: mỗi thư mục mood có ≥1 .mp3 HOẶC SOURCE.txt (phản ánh trạng thái tải thực)
  - unit: CREDITS.txt tồn tại và có entry cho mỗi track mp3 thực sự có
  - integration: tải mp3 qua ffprobe để xác nhận file hợp lệ (skipif thiếu ffprobe)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MUSIC_ROOT = _REPO_ROOT / "assets" / "music"
_CREDITS_PATH = _MUSIC_ROOT / "CREDITS.txt"

_VENDOR_DIR = _REPO_ROOT / "vendor"
import sys
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))


def _mood_keys() -> list[str]:
    """Lấy 6 key taxonomy từ music.py — single source of truth."""
    from videopipe.music import MOOD_TAXONOMY
    return list(MOOD_TAXONOMY.keys())


_FFPROBE_AVAILABLE = shutil.which("ffprobe") is not None


class TestMoodDirectories:
    """Mỗi mood phải có thư mục tương ứng dưới assets/music/."""

    def test_all_mood_dirs_exist(self):
        """assets/music/<mood>/ tồn tại cho mỗi mood trong MOOD_TAXONOMY."""
        missing = []
        for mood in _mood_keys():
            d = _MUSIC_ROOT / mood
            if not d.is_dir():
                missing.append(mood)
        assert not missing, f"Thiếu thư mục mood: {missing}"


class TestMoodContent:
    """Mỗi thư mục mood phải có ≥1 .mp3 hoặc SOURCE.txt (nếu tải bị chặn)."""

    def test_each_mood_has_mp3_or_source_txt(self):
        """Mỗi mood có ≥1 .mp3 (tải được) HOẶC SOURCE.txt (mạng bị chặn)."""
        failing = []
        for mood in _mood_keys():
            d = _MUSIC_ROOT / mood
            if not d.is_dir():
                failing.append(f"{mood}: thư mục không tồn tại")
                continue
            has_mp3 = any(d.glob("*.mp3"))
            has_source = (d / "SOURCE.txt").exists()
            if not (has_mp3 or has_source):
                failing.append(f"{mood}: không có .mp3 và không có SOURCE.txt")
        assert not failing, "Mood không đủ asset:\n" + "\n".join(failing)

    def test_source_txt_has_content_when_no_mp3(self):
        """SOURCE.txt (nếu có) phải không rỗng — phải ghi link + hướng dẫn."""
        for mood in _mood_keys():
            d = _MUSIC_ROOT / mood
            if not d.is_dir():
                continue
            source_file = d / "SOURCE.txt"
            if source_file.exists() and not any(d.glob("*.mp3")):
                content = source_file.read_text(encoding="utf-8").strip()
                assert content, f"{mood}/SOURCE.txt rỗng — phải ghi link Pixabay + hướng dẫn"


class TestCredits:
    """CREDITS.txt phải tồn tại và có entry cho mỗi track mp3 thực sự có."""

    def test_credits_file_exists(self):
        """assets/music/CREDITS.txt phải tồn tại."""
        assert _CREDITS_PATH.exists(), "CREDITS.txt chưa tồn tại"

    def test_credits_has_pixabay_mention(self):
        """CREDITS.txt phải đề cập nguồn Pixabay."""
        content = _CREDITS_PATH.read_text(encoding="utf-8")
        assert "pixabay" in content.lower(), "CREDITS.txt chưa đề cập Pixabay"

    def test_each_mp3_has_credits_entry(self):
        """Mỗi file .mp3 thực sự tải về phải có entry trong CREDITS.txt."""
        credits_text = _CREDITS_PATH.read_text(encoding="utf-8").lower()
        missing_credits = []
        for mood in _mood_keys():
            d = _MUSIC_ROOT / mood
            if not d.is_dir():
                continue
            for mp3 in d.glob("*.mp3"):
                if mp3.stem.lower() not in credits_text and mp3.name.lower() not in credits_text:
                    missing_credits.append(f"{mood}/{mp3.name}")
        assert not missing_credits, (
            "Thiếu entry CREDITS cho:\n" + "\n".join(missing_credits)
        )


@pytest.mark.skipif(
    not _FFPROBE_AVAILABLE,
    reason="ffprobe không có trong PATH — integration test bị CHẶN.",
)
class TestMp3Validity:
    """Integration: mỗi .mp3 tải về phải là file âm thanh hợp lệ theo ffprobe."""

    def test_all_mp3s_are_valid(self):
        """ffprobe duration > 0 cho mỗi .mp3 thực sự có."""
        invalid = []
        for mood in _mood_keys():
            d = _MUSIC_ROOT / mood
            if not d.is_dir():
                continue
            for mp3 in d.glob("*.mp3"):
                result = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "csv=p=0",
                        str(mp3),
                    ],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    invalid.append(f"{mood}/{mp3.name}: ffprobe lỗi — {result.stderr[:200]}")
                    continue
                try:
                    dur = float(result.stdout.strip())
                except ValueError:
                    invalid.append(f"{mood}/{mp3.name}: duration không parse được")
                    continue
                if dur <= 0:
                    invalid.append(f"{mood}/{mp3.name}: duration={dur}s <= 0")
        assert not invalid, "Mp3 không hợp lệ:\n" + "\n".join(invalid)

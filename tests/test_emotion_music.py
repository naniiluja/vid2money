"""Tests cho task 004 — engine nhạc theo cảm xúc.

Bao gồm:
  - unit: resolve_mood (4 nhánh)
  - unit: build_music_timeline (gộp/cắt/tổng)
  - unit: single-source-of-truth (schema enum == taxonomy music.py)
  - integration: desync tường minh bằng ffprobe (fixture synthetic)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills" / "video-storyteller" / "references" / "storyboard.schema.json"
)

# Kiểm tra ffmpeg/ffprobe để báo rõ khi thiếu (không skip âm thầm).
import shutil

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def simple_shot():
    """Shot dataclass tối giản không phụ thuộc pipeline nặng."""
    from videopipe.storyboard import Shot
    return Shot(id=0, narration="test narration", image_prompt="test image")


# ---------------------------------------------------------------------------
# Unit: resolve_mood
# ---------------------------------------------------------------------------

class TestResolveMood:
    def test_valid_mood_field_used_directly(self):
        """shot.mood hợp lệ → dùng nguyên giá trị đó."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="hello world", image_prompt="img", mood="uplifting")
        assert resolve_mood(shot) == "uplifting"

    def test_invalid_mood_label_falls_back_to_keyword(self):
        """shot.mood sai (không có trong taxonomy) → fallback phân tích keyword narration."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="hope and victory triumph", image_prompt="img", mood="INVALID_MOOD")
        result = resolve_mood(shot)
        # Kết quả phải là 1 trong 6 mood hợp lệ.
        from videopipe.music import MOOD_TAXONOMY
        assert result in MOOD_TAXONOMY

    def test_crisis_keyword_maps_to_tense(self):
        """Narration chứa 'khủng hoảng' → tense."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="Đây là khủng hoảng tài chính lớn nhất", image_prompt="img")
        assert resolve_mood(shot) == "tense"

    def test_crisis_english_keyword_maps_to_tense(self):
        """Narration chứa 'crisis' → tense."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="The financial crisis hit everyone hard", image_prompt="img")
        assert resolve_mood(shot) == "tense"

    def test_empty_narration_returns_calm(self):
        """Narration rỗng → calm (default)."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="", image_prompt="img")
        assert resolve_mood(shot) == "calm"

    def test_no_mood_field_empty_narration_returns_calm(self):
        """shot.mood=None và narration rỗng → calm."""
        from videopipe.storyboard import Shot
        from videopipe.music import resolve_mood
        shot = Shot(id=0, narration="   ", image_prompt="img", mood=None)
        assert resolve_mood(shot) == "calm"


# ---------------------------------------------------------------------------
# Unit: build_music_timeline
# ---------------------------------------------------------------------------

class TestBuildMusicTimeline:
    def _make_shot(self, id_: int, narration: str, mood: str | None = None):
        from videopipe.storyboard import Shot
        return Shot(id=id_, narration=narration, image_prompt="img", mood=mood)

    def test_adjacent_same_mood_merged(self):
        """2 shot cùng mood → 1 segment trong timeline."""
        from videopipe.music import build_music_timeline
        shots = [
            self._make_shot(0, "calm text here", mood="calm"),
            self._make_shot(1, "calm narration also", mood="calm"),
        ]
        durations = [5.0, 7.0]
        timeline = build_music_timeline(shots, durations)
        assert len(timeline) == 1
        assert timeline[0]["mood"] == "calm"
        assert timeline[0]["duration"] == pytest.approx(12.0)

    def test_different_moods_not_merged(self):
        """3 shot mood khác nhau → 3 segment."""
        from videopipe.music import build_music_timeline
        shots = [
            self._make_shot(0, "", mood="calm"),
            self._make_shot(1, "triumph", mood="triumphant"),
            self._make_shot(2, "", mood="somber"),
        ]
        durations = [4.0, 6.0, 5.0]
        timeline = build_music_timeline(shots, durations)
        assert len(timeline) == 3
        assert [seg["mood"] for seg in timeline] == ["calm", "triumphant", "somber"]

    def test_cut_points_at_shot_boundaries(self):
        """Điểm cắt (start) khớp ranh giới shot."""
        from videopipe.music import build_music_timeline
        shots = [
            self._make_shot(0, "", mood="calm"),
            self._make_shot(1, "crisis", mood=None),  # fallback tense
            self._make_shot(2, "", mood="uplifting"),
        ]
        durations = [3.0, 4.0, 5.0]
        timeline = build_music_timeline(shots, durations)
        # Mỗi segment có start = tổng duration các shot trước đó
        assert timeline[0]["start"] == pytest.approx(0.0)
        assert timeline[1]["start"] == pytest.approx(3.0)
        assert timeline[2]["start"] == pytest.approx(7.0)

    def test_total_duration_matches_sum(self):
        """Tổng duration các segment trong timeline = tổng duration shots."""
        from videopipe.music import build_music_timeline
        shots = [
            self._make_shot(0, "", mood="calm"),
            self._make_shot(1, "", mood="tense"),
            self._make_shot(2, "", mood="calm"),
        ]
        durations = [3.0, 5.0, 4.0]
        timeline = build_music_timeline(shots, durations)
        total = sum(seg["duration"] for seg in timeline)
        assert total == pytest.approx(sum(durations))

    def test_merge_nonconsecutive_same_mood(self):
        """Mood giống nhau nhưng không liền nhau → KHÔNG gộp."""
        from videopipe.music import build_music_timeline
        shots = [
            self._make_shot(0, "", mood="calm"),
            self._make_shot(1, "", mood="tense"),
            self._make_shot(2, "", mood="calm"),
        ]
        durations = [3.0, 5.0, 4.0]
        timeline = build_music_timeline(shots, durations)
        assert len(timeline) == 3  # không gộp vì không liền kề

    def test_single_shot(self):
        """1 shot → 1 segment."""
        from videopipe.music import build_music_timeline
        shots = [self._make_shot(0, "", mood="playful")]
        durations = [8.0]
        timeline = build_music_timeline(shots, durations)
        assert len(timeline) == 1
        assert timeline[0]["duration"] == pytest.approx(8.0)
        assert timeline[0]["start"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit: single-source-of-truth (enum schema == taxonomy music.py)
# ---------------------------------------------------------------------------

class TestSingleSourceOfTruth:
    def test_schema_mood_enum_matches_taxonomy_keys(self):
        """enum 'mood' trong storyboard.schema.json phải khớp chính xác taxonomy keys trong music.py."""
        from videopipe.music import MOOD_TAXONOMY

        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        # Tìm enum mood trong schema shots.items.properties.mood.enum
        shot_props = schema["properties"]["shots"]["items"]["properties"]
        assert "mood" in shot_props, "Field 'mood' chưa có trong storyboard.schema.json"
        schema_moods = set(shot_props["mood"]["enum"])
        taxonomy_keys = set(MOOD_TAXONOMY.keys())
        assert schema_moods == taxonomy_keys, (
            f"Schema enum {sorted(schema_moods)} "
            f"!= taxonomy keys {sorted(taxonomy_keys)}"
        )


# ---------------------------------------------------------------------------
# Integration: desync tường minh bằng ffprobe (fixture synthetic)
# ---------------------------------------------------------------------------

def _make_synthetic_mp3(path: Path, duration_s: float) -> Path:
    """Tạo file mp3 synthetic bằng ffmpeg sine tone.

    Dùng sine tone 440Hz → mp3 128k. Không phụ thuộc nhạc thật.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_s:.3f}",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi tạo fixture: {result.stderr[-500:]}")
    return path


def _ffprobe_duration(path: Path) -> float:
    """Đọc duration bằng ffprobe — độc lập với pipeline."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe lỗi: {result.stderr}")
    return float(result.stdout.strip())


@pytest.mark.skipif(
    not _FFMPEG_AVAILABLE,
    reason="ffmpeg/ffprobe không có trong PATH — integration test bị CHẶN. Cài ffmpeg rồi chạy lại.",
)
class TestEmotionMusicDesync:
    """Integration test: mix 2+ scene khác mood → assert duration tường minh bằng ffprobe.

    Công thức expected khi acrossfade d=2:
      expected = Σ(dur_shot) − (n_joins × d)
    với n_joins = số mối nối acrossfade = len(timeline_segments) − 1
    và d = 2 (crossfade duration).

    Test này có ≥2 mối acrossfade nên n_joins ≥ 2.
    """

    def test_mix_emotion_tracks_duration_no_desync(self, tmp_path):
        """Mix 3 segment khác mood (2 mối acrossfade) → duration khớp công thức."""
        from videopipe.storyboard import Shot
        from videopipe.music import build_music_timeline
        from videopipe.ffmpeg_ops import mix_emotion_tracks

        FPS = 30
        CROSSFADE_D = 2.0

        # Tạo 3 fixture mp3 synthetic — 3 độ dài khác nhau.
        dur_a = 8.0   # segment nhạc cho mood 1
        dur_b = 10.0  # segment nhạc cho mood 2
        dur_c = 7.0   # segment nhạc cho mood 3
        music_a = _make_synthetic_mp3(tmp_path / "music_calm.mp3", dur_a + 5)
        music_b = _make_synthetic_mp3(tmp_path / "music_tense.mp3", dur_b + 5)
        music_c = _make_synthetic_mp3(tmp_path / "music_uplifting.mp3", dur_c + 5)

        # 3 shot khác mood
        shot_durs = [dur_a, dur_b, dur_c]
        shots = [
            Shot(id=0, narration="calm intro", image_prompt="img", mood="calm"),
            Shot(id=1, narration="crisis danger tense", image_prompt="img", mood="tense"),
            Shot(id=2, narration="hope victory", image_prompt="img", mood="uplifting"),
        ]

        timeline = build_music_timeline(shots, shot_durs)
        assert len(timeline) == 3, "Phải có 3 segment trong timeline (3 mood khác nhau)"

        # Map mood → file nhạc fixture
        mood_files = {
            "calm": music_a,
            "tense": music_b,
            "uplifting": music_c,
        }

        out_mixed = tmp_path / "mixed_music.mp3"
        mix_emotion_tracks(
            timeline=timeline,
            mood_files=mood_files,
            out_audio=out_mixed,
            crossfade_d=CROSSFADE_D,
        )

        assert out_mixed.exists(), "File output mix không được tạo ra"

        actual_dur = _ffprobe_duration(out_mixed)
        # Công thức: Σ(dur_shot) − (n_joins × d)
        # n_joins = 3 - 1 = 2 mối acrossfade
        n_joins = len(timeline) - 1
        expected_dur = sum(shot_durs) - n_joins * CROSSFADE_D
        tol = 1.0 / FPS  # 1 frame tolerance

        assert abs(actual_dur - expected_dur) <= tol, (
            f"Desync: actual={actual_dur:.4f}s, expected={expected_dur:.4f}s, "
            f"diff={abs(actual_dur - expected_dur):.4f}s > tol={tol:.4f}s (1/{FPS}fps). "
            f"Công thức: {sum(shot_durs):.1f} - {n_joins}×{CROSSFADE_D} = {expected_dur:.4f}s"
        )

    def test_mix_two_moods_two_crossfades(self, tmp_path):
        """Mix 4 shot (2 cặp mood khác nhau xen kẽ) → ≥2 mối acrossfade."""
        from videopipe.storyboard import Shot
        from videopipe.music import build_music_timeline
        from videopipe.ffmpeg_ops import mix_emotion_tracks

        FPS = 30
        CROSSFADE_D = 2.0

        shot_durs = [5.0, 6.0, 5.0, 7.0]
        shots = [
            Shot(id=0, narration="", image_prompt="img", mood="calm"),
            Shot(id=1, narration="", image_prompt="img", mood="tense"),
            Shot(id=2, narration="", image_prompt="img", mood="calm"),
            Shot(id=3, narration="", image_prompt="img", mood="uplifting"),
        ]

        music_calm = _make_synthetic_mp3(tmp_path / "calm2.mp3", 20.0)
        music_tense = _make_synthetic_mp3(tmp_path / "tense2.mp3", 15.0)
        music_uplifting = _make_synthetic_mp3(tmp_path / "uplift2.mp3", 15.0)

        timeline = build_music_timeline(shots, shot_durs)
        # 4 shot, xen kẽ mood → không gộp được → 4 segment → 3 mối acrossfade
        assert len(timeline) >= 3, "Phải có ít nhất 3 segment (≥2 mối acrossfade)"

        mood_files = {
            "calm": music_calm,
            "tense": music_tense,
            "uplifting": music_uplifting,
        }

        out_mixed = tmp_path / "mixed2.mp3"
        mix_emotion_tracks(
            timeline=timeline,
            mood_files=mood_files,
            out_audio=out_mixed,
            crossfade_d=CROSSFADE_D,
        )

        assert out_mixed.exists()

        actual_dur = _ffprobe_duration(out_mixed)
        n_joins = len(timeline) - 1
        expected_dur = sum(shot_durs) - n_joins * CROSSFADE_D
        tol = 1.0 / FPS

        assert abs(actual_dur - expected_dur) <= tol, (
            f"Desync: actual={actual_dur:.4f}s, expected={expected_dur:.4f}s, "
            f"diff={abs(actual_dur - expected_dur):.4f}s > tol={tol:.4f}s. "
            f"Công thức: {sum(shot_durs):.1f} - {n_joins}×{CROSSFADE_D} = {expected_dur:.4f}s"
        )

"""Unit test cho ngân sách thời lượng --target-minutes (task 002).

Kiểm tra:
  1. words_per_minute(rate) — dẫn xuất từ BASE_WPM=150.
  2. expected_words(minutes, rate) — ngân sách lời.
  3. is_duration_off(actual_s, target_s, tol) — cảnh báo biên ±10%.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from videopipe.config import BASE_WPM, expected_words, is_duration_off, words_per_minute


# ---------------------------------------------------------------------------
# words_per_minute
# ---------------------------------------------------------------------------

class TestWordsPerMinute:
    def test_plus_5_percent(self):
        result = words_per_minute("+5%")
        assert abs(result - 157.5) < 0.01

    def test_minus_4_percent(self):
        result = words_per_minute("-4%")
        assert abs(result - 144.0) < 0.01

    def test_zero_percent(self):
        result = words_per_minute("+0%")
        assert abs(result - BASE_WPM) < 0.01

    def test_zero_percent_no_sign(self):
        result = words_per_minute("0%")
        assert abs(result - BASE_WPM) < 0.01

    def test_minus_8_percent(self):
        result = words_per_minute("-8%")
        assert abs(result - 138.0) < 0.01

    def test_plus_10_percent(self):
        result = words_per_minute("+10%")
        assert abs(result - 165.0) < 0.01

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            words_per_minute("fast")


# ---------------------------------------------------------------------------
# expected_words
# ---------------------------------------------------------------------------

class TestExpectedWords:
    def test_1_minute_default_rate(self):
        wpm = words_per_minute("-4%")
        result = expected_words(1.0, "-4%")
        assert result == round(1.0 * wpm * 0.88)

    def test_3_minutes_default_rate(self):
        wpm = words_per_minute("-4%")
        result = expected_words(3.0, "-4%")
        assert result == round(3.0 * wpm * 0.88)

    def test_10_minutes_plus5(self):
        wpm = words_per_minute("+5%")
        result = expected_words(10.0, "+5%")
        assert result == round(10.0 * wpm * 0.88)

    def test_2_minutes_zero(self):
        wpm = words_per_minute("+0%")
        result = expected_words(2.0, "+0%")
        assert result == round(2.0 * BASE_WPM * 0.88)


# ---------------------------------------------------------------------------
# is_duration_off
# ---------------------------------------------------------------------------

class TestIsDurationOff:
    """Biên ±10%: actual trong [0.9*target, 1.1*target] → False (không lệch).
    Ngoài biên → True (lệch).
    """

    def test_exact_match(self):
        assert is_duration_off(600.0, 600.0) is False

    def test_within_10_percent_over(self):
        # actual = target * 1.10 — đúng biên, không lệch
        assert is_duration_off(660.0, 600.0) is False

    def test_within_10_percent_under(self):
        # actual = target * 0.90 — đúng biên, không lệch
        assert is_duration_off(540.0, 600.0) is False

    def test_over_11_percent_triggers(self):
        # actual = target * 1.11 — ngoài biên
        assert is_duration_off(666.0, 600.0) is True

    def test_under_11_percent_triggers(self):
        # actual = target * 0.89 — ngoài biên
        assert is_duration_off(534.0, 600.0) is True

    def test_custom_tolerance_5_percent_pass(self):
        # tol=0.05, actual=target*1.05 — đúng biên
        assert is_duration_off(630.0, 600.0, tol=0.05) is False

    def test_custom_tolerance_5_percent_fail(self):
        # tol=0.05, actual=target*1.06 — ngoài biên
        assert is_duration_off(636.0, 600.0, tol=0.05) is True

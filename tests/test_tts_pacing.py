"""Unit test cho task 003 — TTS rate +5% và voice Andrew (không gọi mạng).

Kiểm tra:
  1. PipelineConfig() mặc định có tts_rate == "+5%".
  2. synthesize() có default rate == "+5%" và voice == "en-US-AndrewMultilingualNeural".
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from videopipe.config import PipelineConfig
from videopipe.tts import synthesize


class TestPipelineConfigTtsRate:
    def test_default_tts_rate_is_plus5(self):
        cfg = PipelineConfig(topic="test")
        assert cfg.tts_rate == "+5%"


class TestSynthesizeDefaults:
    def test_default_rate_is_plus5(self):
        sig = inspect.signature(synthesize)
        assert sig.parameters["rate"].default == "+5%"

    def test_default_voice_is_andrew(self):
        sig = inspect.signature(synthesize)
        assert sig.parameters["voice"].default == "en-US-AndrewMultilingualNeural"

"""Unit test cho check_env.probe_environment() — mock mọi I/O ngoài.

Không phụ thuộc ffmpeg/codex thật. Mock shutil.which,
importlib.util.find_spec, platform.system.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Thêm thư mục scripts vào sys.path để import check_env.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills" / "video-storyteller" / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_env  # noqa: E402 — phải sau sys.path


# ---------------------------------------------------------------------------
# Helpers — fixture tái sử dụng
# ---------------------------------------------------------------------------

def _mock_which(available: set[str]):
    """Trả hàm giả shutil.which: trả đường dẫn giả nếu tên trong available."""
    def _which(name: str) -> str | None:
        # 'codex' trên Windows resolve thành 'codex.cmd' — chấp nhận cả hai.
        key = name.lower().replace(".cmd", "")
        return f"/usr/bin/{key}" if key in available else None
    return _which


def _mock_find_spec(available: set[str]):
    """Trả hàm giả importlib.util.find_spec: trả object giả nếu tên trong available."""
    def _find_spec(name: str):
        return MagicMock() if name in available else None
    return _find_spec


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestProbeEnvironment:
    """Kiểm tra probe_environment() với các combo đầu vào khác nhau."""

    def _run(
        self,
        which_available: set[str],
        specs_available: set[str],
        env_overrides: dict[str, str] | None = None,
        platform_system: str = "Linux",
        stdin_fix_ok: bool = True,
    ) -> dict:
        """Chạy probe_environment() với mock đầy đủ (không còn anti2api)."""
        env: dict[str, str] = {}
        if env_overrides:
            env.update(env_overrides)

        with (
            patch("shutil.which", side_effect=_mock_which(which_available)),
            patch(
                "importlib.util.find_spec",
                side_effect=_mock_find_spec(specs_available),
            ),
            patch("check_env._check_vendored_stdin_fix", return_value=stdin_fix_ok),
            patch("os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
            patch("platform.system", return_value=platform_system),
        ):
            return check_env.probe_environment()

    # CA 1: Đủ tool → recommended_backend="codex", không blocker, không key "anti2api"
    def test_all_tools_recommends_codex(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"
        assert result["blockers"] == []
        assert result["tools"]["ffmpeg"] is True
        assert result["tools"]["ffprobe"] is True
        assert result["tools"]["edge-tts"] is True
        # Không còn key anti2api trong tools.
        assert "anti2api" not in result["tools"]

    # CA 2: Thiếu ffmpeg → ffmpeg trong blockers
    def test_missing_ffmpeg_adds_blocker(self):
        result = self._run(
            which_available={"ffprobe", "codex"},
            specs_available={"edge_tts"},
            platform_system="Linux",
        )
        assert result["tools"]["ffmpeg"] is False
        # Phải có ít nhất 1 blocker đề cập ffmpeg.
        ffmpeg_blockers = [b for b in result["blockers"] if "ffmpeg" in b.lower()]
        assert len(ffmpeg_blockers) >= 1

    # CA 3: recommended=codex + platform=Windows → có warning codex-Windows
    def test_codex_backend_windows_adds_warning(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            platform_system="Windows",
            stdin_fix_ok=True,
        )
        assert result["recommended_backend"] == "codex"
        # Phải có warning đề cập context-bleed hoặc CODEX/WINDOWS.
        codex_warnings = [
            w for w in result["warnings"]
            if "context-bleed" in w.lower() or "codex" in w.lower()
        ]
        assert len(codex_warnings) >= 1

    # CA 4: recommended=codex + platform=Linux → KHÔNG có warning codex-Windows
    def test_codex_backend_linux_no_windows_warning(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"
        # Không được có warning nói về CODEX/WINDOWS hay context-bleed.
        codex_windows_warnings = [
            w for w in result["warnings"]
            if "cảnh báo codex/windows" in w.lower() or "CẢNH BÁO CODEX/WINDOWS" in w
        ]
        assert codex_windows_warnings == []

    # CA 5: recommended_backend LUÔN = "codex" — không còn nhánh gemini
    def test_recommended_backend_always_codex(self):
        """Dù env nào, recommended_backend phải là 'codex' (backend gemini đã bỏ ở plugin)."""
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"
        # Không được là "gemini".
        assert result["recommended_backend"] != "gemini"

"""Unit test cho check_env.probe_environment() — mock mọi I/O ngoài.

Không phụ thuộc ffmpeg/codex/anti2api thật. Mock shutil.which,
importlib.util.find_spec, urllib, platform.system.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
import urllib.error
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
        anti2api_alive: bool,
        env_overrides: dict[str, str] | None = None,
        platform_system: str = "Linux",
        stdin_fix_ok: bool = True,
    ) -> dict:
        """Chạy probe_environment() với mock đầy đủ."""
        env = {
            "ANTI2API_BASE_URL": "http://localhost:8046",
            "ANTI2API_KEY": "",
        }
        if env_overrides:
            env.update(env_overrides)

        with (
            patch("shutil.which", side_effect=_mock_which(which_available)),
            patch(
                "importlib.util.find_spec",
                side_effect=_mock_find_spec(specs_available),
            ),
            patch("check_env._probe_anti2api", return_value=anti2api_alive),
            patch("check_env._check_vendored_stdin_fix", return_value=stdin_fix_ok),
            patch("os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
            patch("platform.system", return_value=platform_system),
        ):
            return check_env.probe_environment()

    # CA 1: Đủ tool + anti2api sống + có key → gemini backend, không blocker
    def test_all_tools_anti2api_alive_with_key_recommends_gemini(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=True,
            env_overrides={
                "ANTI2API_BASE_URL": "http://localhost:8046",
                "ANTI2API_KEY": "test-key-abc",
            },
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "gemini"
        assert result["blockers"] == []
        assert result["tools"]["ffmpeg"] is True
        assert result["tools"]["ffprobe"] is True
        assert result["tools"]["edge-tts"] is True
        assert result["tools"]["anti2api"] is True

    # CA 2: Đủ tool + anti2api chết → codex backend
    def test_all_tools_anti2api_dead_recommends_codex(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=False,
            env_overrides={"ANTI2API_KEY": "some-key"},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"
        assert result["blockers"] == []

    # CA 2b: anti2api sống nhưng không có key → codex backend
    def test_anti2api_alive_no_key_recommends_codex(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=True,
            env_overrides={"ANTI2API_KEY": ""},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"

    # CA 3: Thiếu ffmpeg → ffmpeg trong blockers
    def test_missing_ffmpeg_adds_blocker(self):
        result = self._run(
            which_available={"ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=False,
            platform_system="Linux",
        )
        assert result["tools"]["ffmpeg"] is False
        # Phải có ít nhất 1 blocker đề cập ffmpeg.
        ffmpeg_blockers = [b for b in result["blockers"] if "ffmpeg" in b.lower()]
        assert len(ffmpeg_blockers) >= 1

    # CA 4: recommended=codex + platform=Windows → có warning codex-Windows
    def test_codex_backend_windows_adds_warning(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=False,
            env_overrides={"ANTI2API_KEY": ""},
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

    # CA 5: recommended=codex + platform=Linux → KHÔNG có warning codex-Windows
    def test_codex_backend_linux_no_windows_warning(self):
        result = self._run(
            which_available={"ffmpeg", "ffprobe", "codex"},
            specs_available={"edge_tts"},
            anti2api_alive=False,
            env_overrides={"ANTI2API_KEY": ""},
            platform_system="Linux",
        )
        assert result["recommended_backend"] == "codex"
        # Không được có warning nói về CODEX/WINDOWS hay context-bleed.
        codex_windows_warnings = [
            w for w in result["warnings"]
            if "cảnh báo codex/windows" in w.lower() or "CẢNH BÁO CODEX/WINDOWS" in w
        ]
        assert codex_windows_warnings == []


class TestProbeAnti2api:
    """Kiểm tra _probe_anti2api() — server sống/chết qua urllib.

    REGRESSION GUARD (bug 2026-06-16): server trả HTTP 404/401 (không có route
    root, hoặc đòi key) NGHĨA LÀ SỐNG — không được coi mọi exception là chết.
    Chỉ URLError (connection refused/timeout) mới là server chết.
    """

    def test_http_error_means_alive(self):
        """HTTPError (401/404) = server PHẢN HỒI = sống → True."""
        err = urllib.error.HTTPError(
            url="http://localhost:8046/v1/models",
            code=401, msg="Invalid API Key", hdrs=None, fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=err):
            assert check_env._probe_anti2api("http://localhost:8046") is True

    def test_url_error_means_dead(self):
        """URLError (connection refused) = server CHẾT → False."""
        err = urllib.error.URLError("Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            assert check_env._probe_anti2api("http://localhost:8046") is False

    def test_ok_response_means_alive(self):
        """Phản hồi 200 bình thường → True."""
        with patch("urllib.request.urlopen", return_value=MagicMock()):
            assert check_env._probe_anti2api("http://localhost:8046") is True

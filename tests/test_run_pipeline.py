"""Unit test cho run_pipeline — path routing + config building (KHÔNG render thật).

Kiểm tra:
  1. VIDEOPIPE_WORK_ROOT được set = <cwd>/video-out sau khi gọi _resolve_paths().
  2. VIDEOPIPE_ASSETS_ROOT = <plugin_root>/assets — có/không CLAUDE_PLUGIN_ROOT.
  3. PipelineConfig dựng đúng backend, style, music từ args.
  4. run_storyboard được gọi với config đúng (mock).

Không chạy ffmpeg / TTS / codex thật — toàn bộ I/O ngoài đều mock.
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Thêm thư mục scripts vào sys.path để import run_pipeline.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "skills" / "video-storyteller" / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Thêm vendor vào sys.path để import videopipe thật (dùng cho _build_config).
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_DIR = _PLUGIN_ROOT / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))


# ---------------------------------------------------------------------------
# Helper — import/reload module sau khi path đã set
# ---------------------------------------------------------------------------

def _get_run_pipeline():
    """Lấy module run_pipeline (import lần đầu hoặc trả cache)."""
    if "run_pipeline" in sys.modules:
        return sys.modules["run_pipeline"]
    import run_pipeline  # noqa: PLC0415
    return run_pipeline


# ---------------------------------------------------------------------------
# CA 1: VIDEOPIPE_WORK_ROOT = <cwd>/video-out
# ---------------------------------------------------------------------------

class TestResolvePathsWorkRoot:
    """_resolve_paths() phải set VIDEOPIPE_WORK_ROOT = <cwd>/video-out."""

    def test_work_root_equals_cwd_video_out(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """VIDEOPIPE_WORK_ROOT phải là <tmp_path>/video-out sau khi gọi _resolve_paths()."""
        # Xoá env cũ để test sạch.
        monkeypatch.delenv("VIDEOPIPE_WORK_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_ASSETS_ROOT", raising=False)
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        rp = _get_run_pipeline()

        # Gọi _resolve_paths với cwd inject = tmp_path.
        _, _, work_root = rp._resolve_paths(cwd=tmp_path)

        expected = str(tmp_path / "video-out")
        assert os.environ.get("VIDEOPIPE_WORK_ROOT") == expected
        assert str(work_root) == expected

    def test_work_root_injected_not_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Khi inject cwd khác nhau, mỗi lần trả work_root đúng cwd đó."""
        monkeypatch.delenv("VIDEOPIPE_WORK_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_ASSETS_ROOT", raising=False)
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        rp = _get_run_pipeline()

        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"

        rp._resolve_paths(cwd=dir_a)
        assert os.environ.get("VIDEOPIPE_WORK_ROOT") == str(dir_a / "video-out")

        rp._resolve_paths(cwd=dir_b)
        assert os.environ.get("VIDEOPIPE_WORK_ROOT") == str(dir_b / "video-out")


# ---------------------------------------------------------------------------
# CA 2: VIDEOPIPE_ASSETS_ROOT = <plugin_root>/assets
# ---------------------------------------------------------------------------

class TestResolvePathsAssetsRoot:
    """_resolve_paths() phải set VIDEOPIPE_ASSETS_ROOT đúng."""

    def test_assets_root_from_claude_plugin_root_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Khi CLAUDE_PLUGIN_ROOT set, VIDEOPIPE_ASSETS_ROOT = ${CLAUDE_PLUGIN_ROOT}/assets."""
        fake_plugin_root = tmp_path / "my_plugin"
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(fake_plugin_root))
        monkeypatch.delenv("VIDEOPIPE_WORK_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_ASSETS_ROOT", raising=False)

        rp = _get_run_pipeline()
        plugin_root, _, _ = rp._resolve_paths(cwd=tmp_path)

        expected_assets = str(fake_plugin_root / "assets")
        assert os.environ.get("VIDEOPIPE_ASSETS_ROOT") == expected_assets
        assert str(plugin_root) == str(fake_plugin_root)

    def test_assets_root_fallback_from_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Khi CLAUDE_PLUGIN_ROOT KHÔNG set, fallback suy từ __file__ của run_pipeline."""
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_WORK_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_ASSETS_ROOT", raising=False)

        rp = _get_run_pipeline()
        plugin_root, _, _ = rp._resolve_paths(cwd=tmp_path)

        # plugin_root phải là parents[3] từ __file__ của run_pipeline.
        # __file__ = skills/video-storyteller/scripts/run_pipeline.py
        # parents[3] = plugin root (video-storyteller/)
        scripts_dir = Path(rp.__file__).resolve().parent
        expected_plugin_root = scripts_dir.parent.parent.parent
        expected_assets = str(expected_plugin_root / "assets")

        assert os.environ.get("VIDEOPIPE_ASSETS_ROOT") == expected_assets
        assert str(plugin_root) == str(expected_plugin_root)


# ---------------------------------------------------------------------------
# CA 3: PipelineConfig dựng đúng từ args
# ---------------------------------------------------------------------------

class TestBuildConfig:
    """_build_config() phải truyền backend, style, music, outro_text đúng."""

    def _make_args(
        self,
        backend: str = "codex",
        style: str = "stick-figure",
        music: str = "",
        music_duck_db: float | None = None,
        run_id: str = "",
        outro_text: str = "",
    ) -> object:
        """Tạo args namespace giả."""
        import types  # noqa: PLC0415
        ns = types.SimpleNamespace(
            backend=backend,
            style=style,
            music=music,
            music_duck_db=music_duck_db,
            run_id=run_id,
            outro_text=outro_text,
        )
        return ns

    def test_backend_codex(self):
        """image_backend phải là 'codex' khi args.backend='codex'."""
        rp = _get_run_pipeline()
        # Vendor phải có trong sys.path (đã thêm ở top của file test).
        args = self._make_args(backend="codex", run_id="test-run-123")
        cfg = rp._build_config(args, board_title="Test Topic")
        assert cfg.image_backend == "codex"

    def test_style_stick_figure(self):
        """style preset phải là stick-figure khi args.style='stick-figure'."""
        rp = _get_run_pipeline()
        args = self._make_args(style="stick-figure", run_id="test-style-1")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.style.name == "stick-figure-explainer"

    def test_style_cinematic(self):
        """style preset phải là cinematic khi args.style='cinematic'."""
        rp = _get_run_pipeline()
        args = self._make_args(style="cinematic", run_id="test-style-2")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.style.name == "mystery-storytelling"

    def test_music_path_none_when_empty(self):
        """music_path phải là None khi args.music rỗng."""
        rp = _get_run_pipeline()
        args = self._make_args(music="", run_id="test-music-1")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.music_path is None

    def test_music_path_set_when_provided(self, tmp_path: Path):
        """music_path phải là Path(args.music) khi có giá trị."""
        rp = _get_run_pipeline()
        fake_music = tmp_path / "music.mp3"
        args = self._make_args(music=str(fake_music), run_id="test-music-2")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.music_path == fake_music

    def test_outro_text_passed_through(self):
        """outro_text phải được truyền vào PipelineConfig."""
        rp = _get_run_pipeline()
        args = self._make_args(outro_text="Subscribe for more!", run_id="test-outro-1")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.outro_text == "Subscribe for more!"

    def test_run_id_passed_through(self):
        """run_id phải được truyền vào PipelineConfig khi có."""
        rp = _get_run_pipeline()
        args = self._make_args(run_id="my-custom-run")
        cfg = rp._build_config(args, board_title="Test")
        assert cfg.run_id == "my-custom-run"


# ---------------------------------------------------------------------------
# CA 4: main() gọi run_storyboard với config + board đúng
# ---------------------------------------------------------------------------

class TestMainIntegration:
    """main() phải set env đúng và gọi run_storyboard với config đúng."""

    def test_main_sets_env_and_calls_run_storyboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """main() phải:
        - set VIDEOPIPE_WORK_ROOT = <tmp_path>/video-out
        - gọi run_storyboard với config.image_backend = 'codex'
        - trả path final.mp4
        """
        import json  # noqa: PLC0415

        # Tạo storyboard JSON tạm.
        board_data = {
            "title": "Test Board",
            "character_sheet_prompt": "A stick figure",
            "shots": [
                {
                    "id": 0,
                    "narration": "Hello world.",
                    "image_prompt": "A stick figure waving",
                }
            ],
        }
        storyboard_file = tmp_path / "test_board.json"
        storyboard_file.write_text(json.dumps(board_data), encoding="utf-8")

        fake_final = tmp_path / "video-out" / "work" / "run1" / "final.mp4"

        monkeypatch.delenv("VIDEOPIPE_WORK_ROOT", raising=False)
        monkeypatch.delenv("VIDEOPIPE_ASSETS_ROOT", raising=False)
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        rp = _get_run_pipeline()

        # Patch run_storyboard + _resolve_paths để inject cwd.
        captured: dict = {}

        original_resolve = rp._resolve_paths

        def _patched_resolve(cwd: Path | None = None):
            # inject tmp_path làm cwd.
            return original_resolve(cwd=tmp_path)

        mock_run_storyboard = MagicMock(return_value=fake_final)

        with (
            patch.object(rp, "_resolve_paths", side_effect=_patched_resolve),
            patch("videopipe.pipeline.run_storyboard", mock_run_storyboard),
        ):
            # Capture stdout để lấy path output.
            import io  # noqa: PLC0415
            from contextlib import redirect_stdout  # noqa: PLC0415

            buf = io.StringIO()
            with redirect_stdout(buf):
                rp.main([
                    "--storyboard", str(storyboard_file),
                    "--run-id", "run1",
                    "--backend", "codex",
                    "--style", "stick-figure",
                ])

        # Assert VIDEOPIPE_WORK_ROOT = tmp_path/video-out
        assert os.environ.get("VIDEOPIPE_WORK_ROOT") == str(tmp_path / "video-out")

        # Assert run_storyboard được gọi 1 lần.
        assert mock_run_storyboard.call_count == 1
        call_config = mock_run_storyboard.call_args[0][0]
        assert call_config.image_backend == "codex"

        # Assert stdout in ra path final.mp4.
        output = buf.getvalue().strip()
        assert str(fake_final) in output

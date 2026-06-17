"""Test xác nhận images.py chỉ còn backend Codex duy nhất.

Hai assertion:
  1. Source images.py không chứa token backend cũ đã bị purge.
  2. generate_image() gọi subprocess.run (Codex) — không có nhánh backend cũ.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

_IMAGES_PATH = _VENDOR_DIR / "videopipe" / "images.py"

_PURGED_TOKENS = (
    "ge" + "mini",
    "anti" + "2api",
)

_PURGED_ATTRS = (
    "_anti" + "2api" + "_base",
    "_anti" + "2api" + "_key",
    "_build_" + "ge" + "mini" + "_payload",
    "_" + "ge" + "mini" + "_image_model",
    "_gen_" + "ge" + "mini",
)


class TestImagesSourceCodexOnly:
    """images.py không được chứa token backend cũ đã bị purge."""

    def test_no_legacy_backend_tokens_in_source(self):
        source = _IMAGES_PATH.read_text(encoding="utf-8", errors="replace").lower()
        for token in _PURGED_TOKENS:
            assert token not in source, (
                f"images.py vẫn còn token '{token}' — chưa purge xong."
            )


class TestGenerateImageCodexRoute:
    """generate_image() luôn route Codex — không còn hàm backend cũ."""

    def _run_generate(self, tmp_path: Path, backend: str = "codex") -> MagicMock:
        from videopipe.config import StylePreset
        import videopipe.images as img_mod

        out = tmp_path / "out.png"
        fake_png = tmp_path / "fake_ig_0001.png"
        fake_png.write_bytes(b"\x89PNG\r\n")

        def _fake_newest(since: float) -> Path | None:
            return fake_png

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""

        with (
            patch.object(img_mod, "_codex_exe", return_value="codex"),
            patch.object(img_mod, "_neutral_cwd", return_value=tmp_path),
            patch.object(img_mod, "_newest_image_since", side_effect=_fake_newest),
            patch("subprocess.run", return_value=mock_proc) as mock_run,
        ):
            img_mod.generate_image(
                prompt="a test scene",
                out_path=out,
                style=StylePreset(),
                size="1536x1024",
                backend=backend,
            )
            return mock_run

    def test_generate_image_calls_subprocess(self, tmp_path: Path):
        """generate_image() phải gọi subprocess.run ít nhất 1 lần (Codex)."""
        mock_run = self._run_generate(tmp_path)
        assert mock_run.call_count >= 1, "subprocess.run phải được gọi cho Codex"

    def test_generate_image_no_legacy_backend_attrs(self):
        """Các hàm backend cũ phải không còn trong images module."""
        import videopipe.images as img_mod
        for name in _PURGED_ATTRS:
            assert not hasattr(img_mod, name), (
                f"images.py vẫn còn '{name}' — chưa purge."
            )


class TestStdoutPathFallback:
    """_gen_codex phải lấy path ảnh từ stdout của Codex khi dò mtime trượt.

    Bug gặp thật (2026-06-17): Codex gen RC=0 + file ig_*.png CÓ thật, nhưng
    _newest_image_since (so mtime) trả None → _gen_codex raise nhầm "không
    sinh được ảnh". stdout của Codex chứa path (prompt yêu cầu report path)
    nên parse stdout là nguồn đáng tin hơn mtime.
    """

    def test_parse_image_path_from_stdout(self):
        """Hàm thuần trích path ig_*.png từ stdout của Codex."""
        import videopipe.images as img_mod
        stdout = (
            "I generated the image.\n"
            "Saved file path: C:\\Users\\me\\.codex\\generated_images\\abc\\ig_0007.png\n"
            "Done."
        )
        path = img_mod._parse_image_path_from_stdout(stdout)
        assert path is not None
        assert path.name == "ig_0007.png"

    def test_parse_image_path_from_stdout_none(self):
        """Không có path trong stdout → trả None (để fallback mtime)."""
        import videopipe.images as img_mod
        assert img_mod._parse_image_path_from_stdout("no image here") is None

    def test_gen_codex_uses_stdout_when_mtime_misses(self, tmp_path: Path):
        """mtime trượt (_newest_image_since=None) nhưng stdout có path → vẫn copy được."""
        from videopipe.config import StylePreset
        import videopipe.images as img_mod

        out = tmp_path / "out.png"
        real_png = tmp_path / "ig_0042.png"
        real_png.write_bytes(b"\x89PNG\r\n")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = f"Saved file path: {real_png}\n"

        with (
            patch.object(img_mod, "_codex_exe", return_value="codex"),
            patch.object(img_mod, "_neutral_cwd", return_value=tmp_path),
            patch.object(img_mod, "_newest_image_since", return_value=None),
            patch("subprocess.run", return_value=mock_proc),
        ):
            result = img_mod._gen_codex(
                prompt="a test scene",
                out_path=out,
                style=StylePreset(),
                size="1536x1024",
                ref_image=None,
                max_attempts=1,
                timeout_s=10,
            )
        assert result == out
        assert out.exists() and out.stat().st_size > 0

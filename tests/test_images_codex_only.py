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
    """_gen_codex phải lấy path ảnh từ stdout của Codex — bất kể tên file.

    Root cause gặp thật (2026-06-17, verify bằng probe codex exec): Codex skill
    imagegen COPY ảnh vào cwd (_imagegen_cwd) với TÊN MÔ TẢ tự đặt (vd
    'stick-figure-waving-hello.png') và báo path đó trong stdout — KHÔNG phải
    'ig_*.png', và lần exec đó KHÔNG tạo ig_*.png trong generated_images. Vì vậy
    cả _newest_image_since (chỉ quét generated_images/ig_*) lẫn regex chỉ-bắt-ig_
    đều trượt → engine raise nhầm 'không sinh được ảnh', retry 3 lần tốn token.
    Fix: parse BẤT KỲ path .png trong stdout.
    """

    # stdout THẬT đã capture từ codex-cli 0.139.0 (không sửa).
    _REAL_STDOUT = (
        "Saved exactly one generated image here:\n\n"
        "`C:\\Users\\sould\\.codex\\_imagegen_cwd\\stick-figure-waving-hello.png`\n"
    )

    def test_parse_real_codex_stdout(self):
        """stdout thật (tên mô tả, bao backtick) → parse ra đúng path .png."""
        import videopipe.images as img_mod
        path = img_mod._parse_image_path_from_stdout(self._REAL_STDOUT)
        assert path is not None
        assert path.name == "stick-figure-waving-hello.png"

    def test_parse_windows_png_no_ig(self):
        """Path Windows tên bất kỳ (không 'ig_') vẫn parse được."""
        import videopipe.images as img_mod
        path = img_mod._parse_image_path_from_stdout(
            "Done. Saved file path: C:\\tmp\\scene-cool.png"
        )
        assert path is not None and path.name == "scene-cool.png"

    def test_parse_posix_png_no_ig(self):
        """Path POSIX không 'ig_' vẫn parse được."""
        import videopipe.images as img_mod
        path = img_mod._parse_image_path_from_stdout(
            "saved to /home/u/.codex/_imagegen_cwd/hello.png\n"
        )
        assert path is not None and path.name == "hello.png"

    def test_parse_strips_backtick(self):
        """Path bao trong backtick markdown → trả path sạch, không dính backtick."""
        import videopipe.images as img_mod
        path = img_mod._parse_image_path_from_stdout("`C:\\a\\b.png`")
        assert path is not None
        assert "`" not in str(path) and path.name == "b.png"

    def test_parse_none_when_no_png(self):
        """Không có .png trong stdout → None (để fallback mtime)."""
        import videopipe.images as img_mod
        assert img_mod._parse_image_path_from_stdout("no image here") is None

    def test_parse_picks_last_png(self):
        """Nhiều .png (vd ref echo lại) → lấy path CUỐI (ảnh kết quả Codex báo cuối)."""
        import videopipe.images as img_mod
        stdout = (
            "Reference image: C:\\refs\\style_sheet.png\n"
            "Saved exactly one generated image here:\n"
            "`C:\\out\\result.png`\n"
        )
        path = img_mod._parse_image_path_from_stdout(stdout)
        assert path is not None and path.name == "result.png"

    def test_gen_codex_uses_stdout_path(self, tmp_path: Path):
        """_newest_image_since=None nhưng stdout có path file thật → copy, KHÔNG raise."""
        from videopipe.config import StylePreset
        import videopipe.images as img_mod

        out = tmp_path / "out.png"
        real_png = tmp_path / "stick-figure-waving-hello.png"
        real_png.write_bytes(b"\x89PNG\r\n")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = ""
        mock_proc.stdout = f"Saved exactly one generated image here:\n`{real_png}`\n"

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

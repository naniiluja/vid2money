"""Bước [4] images — gen ảnh minh họa qua Codex CLI image_gen.

Backend duy nhất: Codex CLI (gpt-image-2 qua image_gen skill).
  Gọi Codex CLI built-in image_gen qua subprocess. image_gen là tool model TỰ
  QUYẾT GỌI trong agent loop (không phải flag CLI), nên headless có thể không
  sinh ảnh ngay → ta:
    1. Ghi mốc thời gian trước khi gọi.
    2. Gọi `codex exec` với prompt yêu cầu rõ "dùng imagegen skill, sinh và lưu 1 ảnh".
    3. ƯU TIÊN: parse path ig_*.png từ stdout của Codex (prompt yêu cầu report
       path). Fallback: glob ĐỆ QUY ~/.codex/generated_images/**/ig_*.png chọn
       file mtime > mốc. (So-mtime đơn lẻ có thể TRƯỢT dù file có thật.)
    4. Bounded retry nếu không thấy ảnh mới.
    5. Copy ảnh ra out_path.
  Đã verify: ảnh lưu ở ~/.codex/generated_images/<uuid>/ig_*.png ($CODEX_HOME unset).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from videopipe.config import StylePreset

log = logging.getLogger("videopipe")


def _codex_exe() -> str:
    """Đường dẫn thực thi codex (trên Windows là codex.cmd — phải resolve đầy đủ)."""
    exe = shutil.which("codex")
    if exe is None:
        raise RuntimeError("Không tìm thấy 'codex' trong PATH — đã cài Codex CLI chưa?")
    return exe


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))


def _neutral_cwd() -> Path:
    """Thư mục TRUNG LẬP & SẠCH cho codex chạy gen ảnh.

    BẮT BUỘC: nếu chạy trong cwd của project video, Codex đọc context project và
    bỏ qua prompt style (context-bleed → ra ảnh studio/cinematic sai). Chạy từ một
    thư mục tạm trung lập thì Codex tuân prompt đúng (vd người que ra chuẩn).

    ROOT CAUSE QUAN TRỌNG (2026-06-16): chỉ "trung lập" CHƯA đủ — nếu thư mục này
    còn ẢNH của lần gen TRƯỚC (Codex hay tự lưu generated-*.png vào cwd), lần gen
    sau NHÌN THẤY ảnh cũ và BẮT CHƯỚC chúng → bleed sang style cũ (vd ra đài thiên
    văn/đèn bàn thay vì người que). Phải DỌN SẠCH artifact ảnh trong cwd này mỗi
    lần. Ngoài ra đặt AGENTS.md rỗng để Codex không leo lên thư mục cha tìm context.
    """
    d = _codex_home() / "_imagegen_cwd"
    d.mkdir(parents=True, exist_ok=True)
    for junk in list(d.glob("*.png")) + list(d.glob("*.jpg")) + list(d.glob("*.txt")):
        try:
            junk.unlink()
        except OSError:
            pass
    agents_md = d / "AGENTS.md"
    if not agents_md.exists():
        agents_md.write_text(
            "Image generation scratch directory. No project context. "
            "Follow only the user prompt's art style.\n",
            encoding="utf-8",
        )
    return d


def _generated_images_dir() -> Path:
    return _codex_home() / "generated_images"


def _newest_image_since(since: float) -> Path | None:
    """Tìm ảnh ig_*.png mới nhất (mtime > since) trong cây generated_images."""
    root = _generated_images_dir()
    if not root.exists():
        return None
    candidates = [
        p for p in root.glob("**/ig_*.png") if p.stat().st_mtime > since
    ]
    if not candidates:
        candidates = [
            p for p in root.glob("**/*.png") if p.stat().st_mtime > since
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# Regex bắt path file ig_*.png trong stdout của Codex (prompt yêu cầu Codex
# "report the saved file path"). Bắt cả Windows (C:\...\ig_x.png) lẫn POSIX.
_IG_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\r\n\"']*?ig_[^\r\n\"'\\/]*\.png|/[^\r\n\"']*?ig_[^\r\n\"'/]*\.png")


def _parse_image_path_from_stdout(stdout: str) -> Path | None:
    """Trích path ảnh ig_*.png từ stdout của Codex (hàm THUẦN, không đụng FS).

    Đáng tin hơn so-mtime: Codex báo path file đã lưu trong stdout (xem
    _build_prompt — yêu cầu "report the saved file path"). So-mtime có thể
    TRƯỢT (độ phân giải/đồng bộ mtime của filesystem) dù file có thật, gây
    raise nhầm "không sinh được ảnh". Trả path KHỚP regex cuối cùng (mới nhất
    trong log) hoặc None. Việc kiểm tồn tại để caller _gen_codex lo.
    """
    if not isinstance(stdout, str) or not stdout:
        return None
    matches = _IG_PATH_RE.findall(stdout)
    if not matches:
        return None
    return Path(matches[-1].strip().strip("'\""))


def _build_prompt(prompt: str, style: StylePreset, size: str, ref_image: Path | None) -> str:
    """Dựng prompt cho skill imagegen.

    NGUYÊN TẮC (đã verify 2026-06-16): gpt-image-2 (như mọi diffusion model) KHÔNG
    hiểu phủ định tốt — liệt kê "Avoid: photorealism, 3D, cinematic, studios, YouTube"
    PHẢN TÁC DỤNG: model thấy các token đó và VẼ CHÍNH CHÚNG (ra ảnh đèn bàn / thành
    phố / đài thiên văn photorealistic thay vì người que). Lệnh shell ngắn — chỉ
    nêu style anchor + scene, KHÔNG có danh sách cấm — ra người que CHUẨN.
    → Dựng prompt POSITIVE-ONLY, ngắn gọn, để style anchor thống trị.
    """
    ref_line = (
        "Match the art style and character of the provided reference image (Image 1).\n"
        if ref_image
        else ""
    )
    return (
        "Use the imagegen skill to generate EXACTLY ONE image and save it.\n"
        f"THE ART STYLE IS MANDATORY: {style.image_style_anchor}.\n"
        f"Scene to draw IN THAT STYLE: {prompt}.\n"
        f"{ref_line}"
        "A single clear scene with generous empty space, drawn entirely in the art "
        "style above.\n"
        f"Size: {size}\n"
        "After generating, report the saved file path."
    )


def _gen_codex(
    prompt: str,
    out_path: Path,
    style: StylePreset,
    size: str,
    ref_image: Path | None,
    max_attempts: int,
    timeout_s: int,
) -> Path:
    """Gen ảnh qua Codex CLI image_gen.

    Giữ nguyên toàn bộ hành vi: prompt qua STDIN (chống context-bleed
    trên Windows), neutral cwd, bounded retry, copy artifact ra out_path.
    """
    full_prompt = _build_prompt(prompt, style, size, ref_image)

    for attempt in range(1, max_attempts + 1):
        since = time.time() - 1.0
        cmd = [
            _codex_exe(), "exec", "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check", "-C", str(_neutral_cwd()),
        ]
        if ref_image is not None:
            cmd += ["-i", str(ref_image), "-"]
        else:
            cmd += ["-"]
        stdin_data = full_prompt

        log.info("image_gen codex (lần %d/%d): %s", attempt, max_attempts, prompt[:60])
        stdout = ""
        try:
            proc = subprocess.run(
                cmd, input=stdin_data, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_s,
                cwd=str(_neutral_cwd()),
            )
            stdout = proc.stdout or ""
            if proc.returncode != 0:
                log.warning("codex exit %d: %s", proc.returncode, proc.stderr[-500:])
        except subprocess.TimeoutExpired:
            log.warning("Lần %d timeout sau %ds, thử lại...", attempt, timeout_s)

        # Ưu tiên path từ stdout (đáng tin hơn so-mtime — xem
        # _parse_image_path_from_stdout); fallback dò mtime nếu stdout không
        # cho path tồn tại.
        from_stdout = _parse_image_path_from_stdout(stdout)
        if from_stdout is not None and not (
            from_stdout.exists() and from_stdout.stat().st_size > 0
        ):
            from_stdout = None
        new_image = from_stdout or _newest_image_since(since)
        if new_image is not None:
            shutil.copy2(new_image, out_path)
            log.info("Ảnh: %s ← %s", out_path.name, new_image)
            return out_path

        log.warning("Lần %d không sinh được ảnh mới, thử lại...", attempt)

    raise RuntimeError(
        f"codex image_gen không sinh được ảnh sau {max_attempts} lần cho prompt: {prompt[:80]}"
    )


def generate_image(
    prompt: str,
    out_path: Path,
    style: StylePreset,
    size: str = "1536x1024",
    ref_image: Path | None = None,
    max_attempts: int = 3,
    timeout_s: int = 480,
    resume: bool = True,
    backend: str = "codex",
) -> Path:
    """Gen 1 ảnh từ prompt, copy ra out_path. Raise nếu thất bại.

    resume=True: nếu out_path đã tồn tại (kích thước > 0) thì bỏ qua, không gen lại
    → cho phép chạy lại pipeline video dài mà không làm lại ảnh đã có.

    backend: luôn "codex" — tham số giữ lại để tương thích chữ ký gọi từ pipeline.
    """
    if resume and out_path.exists() and out_path.stat().st_size > 0:
        log.info("image (skip, đã có): %s", out_path.name)
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    return _gen_codex(prompt, out_path, style, size, ref_image, max_attempts, timeout_s)

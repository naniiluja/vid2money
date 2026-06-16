"""Bước [4] images — gen ảnh minh họa, hỗ trợ 2 backend.

Backend "codex" (mặc định):
  Gọi Codex CLI built-in image_gen qua subprocess. image_gen là tool model TỰ
  QUYẾT GỌI trong agent loop (không phải flag CLI), nên headless có thể không
  sinh ảnh ngay → ta:
    1. Ghi mốc thời gian trước khi gọi.
    2. Gọi `codex exec` với prompt yêu cầu rõ "dùng imagegen skill, sinh và lưu 1 ảnh".
    3. Glob ĐỆ QUY ~/.codex/generated_images/**/ig_*.png, chọn file mtime > mốc.
    4. Bounded retry nếu không thấy ảnh mới.
    5. Copy ảnh ra out_path.
  Đã verify: ảnh lưu ở ~/.codex/generated_images/<uuid>/ig_*.png ($CODEX_HOME unset).

Backend "gemini":
  POST đến anti2api /v1/chat/completions với model gemini-3-pro-image.
  API key đọc từ env ANTI2API_KEY; base URL từ ANTI2API_BASE_URL (mặc định
  http://localhost:8046). Server trả Markdown ![image](URL) trong content →
  parse URL → tải ảnh về out_path qua urllib.request (không thêm dep ngoài).
  Hỗ trợ img2img (task 103b): truyền ref_image=Path → encode base64 →
  dựng content multimodal [{type:text,...},{type:image_url,...}] theo spec
  OpenAI Image Input trong API.md. Khi không có ref_image: content vẫn là
  string (không regress 103).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from videopipe.config import StylePreset

log = logging.getLogger("videopipe")

# URL mặc định của anti2api (override bằng env ANTI2API_BASE_URL).
_DEFAULT_ANTI2API_BASE = "http://localhost:8046"

# Model mặc định cho image gen. API.md ghi "gemini-3-pro-image" nhưng alias đó trả
# 404 trên server anti2api hiện tại (2026-06-16) — model THẬT chạy được là
# "gemini-3.1-flash-image". Override bằng env ANTI2API_IMAGE_MODEL nếu server đổi.
_DEFAULT_GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"

# Timeout (giây) cho mỗi request đến anti2api (POST + GET ảnh riêng).
_GEMINI_TIMEOUT_S = 180


# ---------------------------------------------------------------------------
# Helpers — Backend Codex
# ---------------------------------------------------------------------------

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
    # Dọn mọi ảnh/text rác lần trước để Codex không bắt chước (chống bleed).
    for junk in list(d.glob("*.png")) + list(d.glob("*.jpg")) + list(d.glob("*.txt")):
        try:
            junk.unlink()
        except OSError:
            pass
    # Chặn Codex đọc context từ thư mục cha.
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
        # Một số bản Codex đặt tên khác — fallback bắt mọi .png mới.
        candidates = [
            p for p in root.glob("**/*.png") if p.stat().st_mtime > since
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


# ---------------------------------------------------------------------------
# Helpers — Backend Gemini (anti2api)
# ---------------------------------------------------------------------------

def _anti2api_base() -> str:
    """Đọc base URL anti2api từ env, mặc định http://localhost:8046."""
    return os.environ.get("ANTI2API_BASE_URL", _DEFAULT_ANTI2API_BASE).rstrip("/")


def _anti2api_key() -> str:
    """Đọc API key từ env ANTI2API_KEY. Raise RuntimeError nếu chưa set."""
    key = os.environ.get("ANTI2API_KEY", "")
    if not key:
        raise RuntimeError(
            "Biến môi trường ANTI2API_KEY chưa được set. "
            "Chạy: export ANTI2API_KEY=<key> (lấy từ D:\\projects\\anti2api\\.env)."
        )
    return key


def _parse_image_url_from_markdown(text: str) -> str | None:
    """Trích URL ảnh đầu tiên từ Markdown dạng ![...](URL).

    Trả None nếu không tìm thấy.
    """
    # Regex bắt mọi dạng ![alt text](URL) — không giới hạn alt text là 'image'
    match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if match:
        return match.group(1)
    return None


def _gemini_image_model() -> str:
    """Đọc tên model image gen từ env, mặc định gemini-3-pro-image."""
    return os.environ.get("ANTI2API_IMAGE_MODEL", _DEFAULT_GEMINI_IMAGE_MODEL)


def _mime_from_suffix(suffix: str) -> str:
    """Trả MIME type từ đuôi file ảnh (vd '.png' → 'image/png').

    Hỗ trợ: png, jpg, jpeg, webp. Đuôi không khớp → mặc định 'image/png'.
    """
    mapping: dict[str, str] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    return mapping.get(suffix.lower(), "image/png")


def _build_gemini_payload(
    prompt_text: str,
    ref_image: Path | None = None,
) -> dict[str, Any]:
    """Dựng body JSON cho POST /v1/chat/completions với model image gen Gemini.

    Tên model mặc định là gemini-3-pro-image (theo spec API.md); override được
    bằng env ANTI2API_IMAGE_MODEL nếu server dùng alias khác.
    prompt_text: chuỗi prompt đã dựng (style anchor + scene description).
    stream=False để nhận response đầy đủ, không parse SSE.

    ref_image (task 103b): nếu truyền, đọc file → encode base64 → dựng content
    multimodal theo OpenAI Image Input format (API.md):
      content = [
        {"type": "text", "text": <prompt_text>},
        {"type": "image_url", "image_url": {"url": "data:image/<mime>;base64,<b64>"}},
      ]
    Khi không có ref_image: content vẫn là string (không regress 103).
    """
    if ref_image is not None:
        # Encode base64 reference image để gửi qua multimodal content.
        img_bytes = ref_image.read_bytes()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        mime = _mime_from_suffix(ref_image.suffix)
        content: str | list[dict[str, Any]] = [
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            },
        ]
    else:
        content = prompt_text

    return {
        "model": _gemini_image_model(),
        "messages": [
            {"role": "user", "content": content},
        ],
        "stream": False,
    }


# ---------------------------------------------------------------------------
# Debug helper — in repr payload rút gọn (chống context-bleed)
# ---------------------------------------------------------------------------

def _log_payload_debug(payload: dict[str, Any]) -> None:
    """In repr rút gọn payload để xác minh ref_image ĐÃ được gắn vào request.

    Theo debugging.md: khi nghi backend bỏ context, in repr request thật thay
    vì đoán. Phần base64 bị truncate (chỉ giữ 40 ký tự đầu) để không làm ngập
    log. KHÔNG in Authorization key.
    """
    msgs = payload.get("messages", [])
    for i, msg in enumerate(msgs):
        content = msg.get("content")
        if isinstance(content, list):
            truncated_parts = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    # Truncate base64 dài, giữ prefix để xác nhận data URI đúng
                    if len(url) > 60:
                        url_short = url[:60] + f"...<{len(url)} chars total>"
                    else:
                        url_short = url
                    truncated_parts.append({
                        "type": "image_url",
                        "image_url": {"url": url_short},
                    })
                else:
                    truncated_parts.append(part)
            log.debug(
                "[payload debug] messages[%d] content (list, %d parts): %r",
                i, len(content), truncated_parts,
            )
        else:
            log.debug(
                "[payload debug] messages[%d] content (str, %d chars): %.80r",
                i, len(content) if content else 0, content,
            )


# ---------------------------------------------------------------------------
# Hàm gen ảnh từng backend
# ---------------------------------------------------------------------------

def _gen_codex(
    prompt: str,
    out_path: Path,
    style: StylePreset,
    size: str,
    ref_image: Path | None,
    max_attempts: int,
    timeout_s: int,
) -> Path:
    """Gen ảnh qua Codex CLI image_gen (backend mặc định).

    Giữ nguyên toàn bộ hành vi cũ kể cả: prompt qua STDIN (chống context-bleed
    trên Windows), neutral cwd, bounded retry, copy artifact ra out_path.
    """
    full_prompt = _build_prompt(prompt, style, size, ref_image)

    for attempt in range(1, max_attempts + 1):
        since = time.time() - 1.0  # trừ 1s phòng lệch đồng hồ
        cmd = [
            _codex_exe(), "exec", "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check", "-C", str(_neutral_cwd()),
        ]
        # ROOT CAUSE context-bleed (verify 2026-06-16): trên Windows codex là
        # `codex.CMD`; truyền prompt DÀI nhiều dòng làm POSITIONAL arg qua subprocess
        # → cmd.exe cắt xén prompt (mất xuống dòng/ký tự đặc biệt) → Codex chỉ nhận
        # mẩu vụn, MẤT style anchor → tự bịa cảnh ngẫu nhiên (pha lê/đèn bàn 3D),
        # ảnh sai cả kích thước. FIX: LUÔN truyền prompt qua STDIN + '-' (an toàn,
        # không qua dòng lệnh .CMD) cho CẢ hai nhánh có/không ref_image.
        if ref_image is not None:
            cmd += ["-i", str(ref_image), "-"]
        else:
            cmd += ["-"]
        stdin_data = full_prompt

        log.info("image_gen codex (lần %d/%d): %s", attempt, max_attempts, prompt[:60])
        try:
            proc = subprocess.run(
                cmd, input=stdin_data, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_s,
                cwd=str(_neutral_cwd()),  # chạy process từ cwd trung lập (chống context-bleed)
            )
            if proc.returncode != 0:
                log.warning("codex exit %d: %s", proc.returncode, proc.stderr[-500:])
        except subprocess.TimeoutExpired:
            # Codex đôi khi treo/quá lâu — coi như 1 lần fail và thử lại,
            # KHÔNG để crash cả pipeline video dài. Nhưng ảnh có thể đã sinh xong
            # ngay trước timeout → vẫn kiểm tra _newest_image_since bên dưới.
            log.warning("Lần %d timeout sau %ds, thử lại...", attempt, timeout_s)

        new_image = _newest_image_since(since)
        if new_image is not None:
            shutil.copy2(new_image, out_path)
            log.info("Ảnh: %s ← %s", out_path.name, new_image)
            return out_path

        log.warning("Lần %d không sinh được ảnh mới, thử lại...", attempt)

    raise RuntimeError(
        f"codex image_gen không sinh được ảnh sau {max_attempts} lần cho prompt: {prompt[:80]}"
    )


def _gen_gemini(
    prompt: str,
    out_path: Path,
    style: StylePreset,
    size: str,
    ref_image: Path | None = None,
) -> Path:
    """Gen ảnh text→image qua anti2api gemini-3-pro-image.

    Đọc ANTI2API_KEY và ANTI2API_BASE_URL từ env.
    Timeout mỗi request: _GEMINI_TIMEOUT_S (180s).
    Lỗi kết nối / HTTP / timeout → RuntimeError rõ (không log key).
    """
    key = _anti2api_key()  # raise RuntimeError nếu thiếu — trước khi gọi mạng
    base = _anti2api_base()
    endpoint = f"{base}/v1/chat/completions"

    # Dựng prompt text cho Gemini — dùng style anchor + scene mô tả cụ thể.
    # Không wrap thêm "Use imagegen skill" vì Gemini-3-pro-image là model
    # text→image trực tiếp (không phải agent), không cần lệnh gọi skill.
    style_anchor = style.image_style_anchor if style else ""
    prompt_text = (
        f"THE ART STYLE IS MANDATORY: {style_anchor}. "
        f"Scene to draw IN THAT STYLE: {prompt}. "
        "A single clear scene with generous empty space, drawn entirely in the art "
        f"style above. Size: {size}"
    ) if style_anchor else prompt

    payload = _build_gemini_payload(prompt_text, ref_image=ref_image)
    body_bytes = json.dumps(payload).encode("utf-8")

    # Log INFO: model + base URL (KHÔNG log key).
    # DEBUG: in repr rút gọn payload để chứng minh ref đã được gắn vào (chống
    # context-bleed — bài học debugging.md: khi nghi backend bỏ context, xác
    # minh bằng repr request thật, không đoán). Base64 bị truncate để không
    # làm ngập log; chỉ cần xác nhận type=image_url có mặt trong content.
    if ref_image is not None:
        _log_payload_debug(payload)
    log.info(
        "image_gen gemini: model=%s base=%s ref=%s prompt=%.60s",
        _gemini_image_model(), base,
        ref_image.name if ref_image else "None",
        prompt,
    )

    # Tạo request với header Authorization Bearer (key không được ghi vào log/exception).
    req = urllib.request.Request(
        endpoint,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_GEMINI_TIMEOUT_S) as resp:
            resp_bytes = resp.read()
    except urllib.error.HTTPError as exc:
        # KHÔNG đưa key vào message lỗi dù code 401.
        raise RuntimeError(
            f"anti2api trả HTTP {exc.code} ({exc.reason}) khi POST {endpoint}. "
            "Kiểm tra ANTI2API_KEY, server đang chạy chưa (chạy anti2api ở cổng "
            f"{base.split(':')[-1] if ':' in base else '8046'})."
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Không kết nối được anti2api tại {base} (timeout={_GEMINI_TIMEOUT_S}s). "
            f"Chi tiết: {exc}. "
            "Chạy anti2api trước: cd D:\\projects\\anti2api && npm start"
        ) from exc

    # Parse response JSON → trích content của assistant.
    try:
        resp_data = json.loads(resp_bytes.decode("utf-8"))
        content = resp_data["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(
            f"anti2api trả response không đúng format: {resp_bytes[:200]!r}"
        ) from exc

    # Trích URL ảnh từ Markdown content.
    image_url = _parse_image_url_from_markdown(content)
    if not image_url:
        raise RuntimeError(
            f"anti2api không trả Markdown ảnh. Content nhận được: {content[:200]!r}"
        )

    log.info("image_gen gemini: nhận URL ảnh %s", image_url)

    # Tải ảnh về out_path.
    try:
        with urllib.request.urlopen(image_url, timeout=_GEMINI_TIMEOUT_S) as img_resp:
            img_bytes = img_resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Không tải được ảnh từ {image_url}: {exc}"
        ) from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img_bytes)
    log.info("Ảnh gemini: %s (%d bytes)", out_path.name, len(img_bytes))
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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

    backend: "codex" (mặc định) hoặc "gemini" (anti2api gemini-3-pro-image).
    Nên truyền config.image_backend xuống đây từ pipeline/orchestrator.
    """
    if resume and out_path.exists() and out_path.stat().st_size > 0:
        log.info("image (skip, đã có): %s", out_path.name)
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if backend == "gemini":
        return _gen_gemini(prompt, out_path, style, size, ref_image)

    # Backend mặc định: Codex
    return _gen_codex(prompt, out_path, style, size, ref_image, max_attempts, timeout_s)

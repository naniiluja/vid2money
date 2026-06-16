"""Bước [2] script — sinh kịch bản kể chuyện (JSON) từ một chủ đề qua Codex.

Schema ScriptDoc:
  {
    "title": str,
    "hook": str,
    "character_sheet_prompt": str,   # prompt tả nhân vật/không khí chung → style sheet
    "scenes": [ { "id": int, "narration": str(EN), "image_prompt": str }, ... ]
  }

character_sheet_prompt được dùng để gen TRƯỚC một "style sheet" image, rồi truyền
làm reference image cho từng scene → nhân vật/bối cảnh nhất quán.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("videopipe")


@dataclass
class Scene:
    id: int
    narration: str
    image_prompt: str


@dataclass
class ScriptDoc:
    title: str
    hook: str
    character_sheet_prompt: str
    scenes: list[Scene]

    @classmethod
    def from_dict(cls, data: dict) -> "ScriptDoc":
        scenes = [
            Scene(id=int(s["id"]), narration=s["narration"], image_prompt=s["image_prompt"])
            for s in data["scenes"]
        ]
        return cls(
            title=data["title"],
            hook=data.get("hook", ""),
            character_sheet_prompt=data["character_sheet_prompt"],
            scenes=scenes,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "hook": self.hook,
                "character_sheet_prompt": self.character_sheet_prompt,
                "scenes": [vars(s) for s in self.scenes],
            },
            ensure_ascii=False,
            indent=2,
        )


def _codex_exe() -> str:
    exe = shutil.which("codex")
    if exe is None:
        raise RuntimeError("Không tìm thấy 'codex' trong PATH.")
    return exe


def _extract_json(text: str) -> dict:
    """Bóc object JSON từ output codex (có thể bọc trong ```json ... ```)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    # Fallback: lấy từ '{' đầu tiên tới '}' cuối cùng.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Không tìm thấy JSON trong output codex:\n{text[:500]}")
    return json.loads(text[start : end + 1])


_SCHEMA_PATH = Path(__file__).with_name("script_schema.json")


def _build_prompt(topic: str, n_scenes: int, style_anchor: str, evidence: str = "") -> str:
    # Prompt tự đóng kín, dứt khoát — KHÔNG hỏi lại, KHÔNG preamble.
    # Shape do --output-schema ép, nên ở đây chỉ cần mô tả nội dung.
    evidence_block = (
        f"Real-world context to draw inspiration from (optional): {evidence}\n"
        if evidence
        else ""
    )
    return (
        "Write a complete short narrated storytelling video script now. "
        "Do not ask any questions; use exactly the inputs below.\n"
        f"STORY TOPIC: {topic}\n"
        f"{evidence_block}"
        f"Language: English. Tone: mysterious, atmospheric. "
        f"Number of scenes: exactly {n_scenes} (ids 0..{n_scenes - 1}).\n"
        "Each scene narration: 2-3 spoken sentences (~6-12 seconds).\n"
        "character_sheet_prompt: one image prompt describing the recurring main "
        "subject and overall visual world (a style reference sheet).\n"
        "Each image_prompt: one concrete single scene, no text/logos/UI, "
        f"consistent visual style: {style_anchor}. Keep the same character look across scenes.\n"
        "This is fiction about the given topic; ignore the working directory name "
        "(it is NOT about YouTube or software)."
    )


def generate_script(
    topic: str,
    out_path: Path,
    n_scenes: int = 4,
    style_anchor: str = "",
    evidence: str = "",
    timeout_s: int = 420,
) -> ScriptDoc:
    """Gọi Codex sinh kịch bản JSON, lưu ra out_path, trả về ScriptDoc.

    Dùng --output-last-message để lấy message cuối SẠCH (stdout của codex exec
    lẫn rất nhiều skill-docs/system-prompt nhiễu, không parse được).
    """
    prompt = _build_prompt(topic, n_scenes, style_anchor, evidence)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    last_msg = out_path.parent / "_codex_last.txt"

    proc = subprocess.run(
        [
            _codex_exe(), "exec", "--dangerously-bypass-approvals-and-sandbox",
            "--output-schema", str(_SCHEMA_PATH),
            "-o", str(last_msg), prompt,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"codex exit {proc.returncode}: {proc.stderr[-500:]}")

    raw = last_msg.read_text(encoding="utf-8") if last_msg.exists() else proc.stdout
    last_msg.unlink(missing_ok=True)
    data = _extract_json(raw)
    doc = ScriptDoc.from_dict(data)

    # Codex đôi khi tạo nhiều scene hơn yêu cầu — cắt về đúng n_scenes, reindex 0..n-1.
    if len(doc.scenes) > n_scenes:
        log.info("Cắt %d → %d scene theo yêu cầu", len(doc.scenes), n_scenes)
        doc.scenes = doc.scenes[:n_scenes]
    for new_id, scene in enumerate(doc.scenes):
        scene.id = new_id

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc.to_json(), encoding="utf-8")
    log.info("Script: %s (%d scenes) — %s", out_path.name, len(doc.scenes), doc.title)
    return doc

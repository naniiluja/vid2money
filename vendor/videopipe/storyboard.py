"""Storyboard — kịch bản dài do Claude (điều phối) tự viết, KHÔNG qua Codex.

Khác với script_gen (gọi Codex sinh JSON), storyboard là file JSON do người/Claude
soạn trực tiếp, cho phép kiểm soát chất lượng + làm video dài (~10 phút) mạch lạc.

Cấu trúc:
  {
    "title": str,
    "style_anchor": str,                 # ghi đè style mặc định (tùy chọn)
    "character_sheet_prompt": str,       # gen style sheet làm reference
    "shots": [
      {
        "id": int,
        "narration": str,                # lời kể (EN) — quyết định thời lượng shot
        "image_prompt": str,             # tả 1 cảnh cụ thể
        "images": int                    # số ảnh cho shot này (mặc định 1);
                                         #   >1 → chia đều thời lượng, đổi ảnh giữa shot
      }
    ]
  }

"images" cho phép "tự động theo nội dung": đoạn cao trào đặt images=2-3 (đổi ảnh
nhanh), đoạn dẫn dắt để images=1 (1 ảnh Ken Burns lâu).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Shot:
    id: int
    narration: str
    image_prompt: str
    images: int = 1


@dataclass
class Storyboard:
    title: str
    character_sheet_prompt: str
    shots: list[Shot]
    style_anchor: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Storyboard":
        shots = [
            Shot(
                id=int(s.get("id", idx)),
                narration=s["narration"],
                image_prompt=s["image_prompt"],
                images=int(s.get("images", 1)),
            )
            for idx, s in enumerate(data["shots"])
        ]
        # reindex liên tục 0..n-1 để chắc chắn không trùng
        for new_id, shot in enumerate(shots):
            shot.id = new_id
        return cls(
            title=data["title"],
            character_sheet_prompt=data["character_sheet_prompt"],
            shots=shots,
            style_anchor=data.get("style_anchor", ""),
        )

    @classmethod
    def load(cls, path: Path) -> "Storyboard":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @property
    def total_images(self) -> int:
        return sum(max(1, s.images) for s in self.shots)

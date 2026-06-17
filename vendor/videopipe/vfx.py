"""Lớp VFX hài tiết chế — builder filter chuỗi ffmpeg duration-preserving.

build_vfx_filters: nhận danh sách annotation của 1 shot, trả chuỗi filter
ffmpeg (để nối vào -vf). Mọi effect bọc enable='between(t,a,b)' để giữ
frame count bất biến. zoompan punch dùng d=1. setpts bị cấm (đổi duration).
Cap tối đa 3 beat/shot (rule-of-three — punctuation, không phải decoration).

Bộ effect:
  pop   — drawtext fontsize expr to-nhỏ (0.3-0.5s)
  punch — zoompan zoom nhanh d=1 (không dùng setpts)
  shake — crop sin offset (mô phỏng rung)
  emoji — drawtext ký tự emoji (nếu font hỗ trợ)
"""

from __future__ import annotations

_MAX_BEATS_PER_SHOT = 3


def _check_setpts(annotation: dict) -> None:
    """Guard: raise ValueError nếu bất kỳ field nào trong annotation chứa 'setpts'.

    setpts thay đổi PTS → đổi duration → vi phạm bất biến duration-preserving.
    """
    for value in annotation.values():
        if isinstance(value, str) and "setpts" in value.lower():
            raise ValueError(
                f"annotation chứa 'setpts' → vi phạm duration-preserving. "
                f"Annotation: {annotation}"
            )


def _pop_filter(text: str, start: float, duration: float) -> str:
    """drawtext pop — fontsize lớn rồi nhỏ lại trong cửa sổ [start, start+duration].

    fontsize dùng expr tuyến tính: to lớn ở giữa, nhỏ hai đầu.
    enable='between(t,a,b)' giữ frame count bất biến.
    """
    end = start + duration
    escaped = text.replace("'", "\\'").replace(":", "\\:")
    mid = start + duration / 2.0
    fontsize_expr = (
        f"72+30*if(between(t,{start:.3f},{mid:.3f}),"
        f"(t-{start:.3f})/{duration/2:.3f},"
        f"if(between(t,{mid:.3f},{end:.3f}),"
        f"({end:.3f}-t)/{duration/2:.3f},0))"
    )
    return (
        f"drawtext=text='{escaped}'"
        f":fontsize='{fontsize_expr}'"
        f":fontcolor=white"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _punch_filter(start: float, duration: float, width: int = 1920, height: int = 1080) -> str:
    """zoompan punch — zoom nhanh vào tâm rồi ra, d=1 (1 frame, không đổi duration).

    d=1 bắt buộc: zoompan với d lớn hơn sẽ thay đổi số frame output.
    enable='between(t,a,b)' bảo vệ thêm.
    """
    end = start + duration
    zoom_expr = (
        f"if(between(t,{start:.3f},{end:.3f}),"
        f"min(zoom+0.05,1.15),max(zoom-0.05,1.0))"
    )
    return (
        f"zoompan=z='{zoom_expr}'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d=1:s={width}x{height}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _shake_filter(start: float, duration: float, amplitude: int = 8) -> str:
    """crop sin-offset — dịch chuyển hình theo hàm sin trong cửa sổ thời gian.

    crop giữ kích thước output bằng input → frame count bất biến.
    enable='between(t,a,b)' chỉ kích hoạt trong cửa sổ.
    """
    end = start + duration
    freq = 30.0
    x_expr = (
        f"if(between(t,{start:.3f},{end:.3f}),"
        f"{amplitude}*sin(2*PI*{freq}*(t-{start:.3f})),0)"
    )
    y_expr = (
        f"if(between(t,{start:.3f},{end:.3f}),"
        f"{amplitude//2}*sin(2*PI*{freq}*(t-{start:.3f})+PI/3),0)"
    )
    return (
        f"crop=w=iw-{amplitude*2}:h=ih-{amplitude}:"
        f"x='{amplitude}+{x_expr}':y='{amplitude//2}+{y_expr}'"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def _emoji_filter(emoji: str, start: float, duration: float) -> str:
    """drawtext emoji — hiển thị ký tự emoji ở góc trên phải trong cửa sổ.

    enable='between(t,a,b)' giữ frame count bất biến.
    """
    end = start + duration
    escaped = emoji.replace("'", "\\'").replace(":", "\\:")
    return (
        f"drawtext=text='{escaped}'"
        f":fontsize=80"
        f":x=w-text_w-40:y=40"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def build_vfx_filters(
    annotations: list[dict],
    enabled: bool = True,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Dựng chuỗi filter VFX ffmpeg từ danh sách annotation của 1 shot.

    Tham số:
        annotations: list annotation, mỗi phần tử có ít nhất {'type', 'at'}.
          - type: 'pop' | 'punch' | 'shake' | 'emoji'
          - at: float (giây, thời điểm bắt đầu trong segment)
          - duration: float (giây, mặc định 0.4)
          - text: str (cho pop/emoji)
        enabled: False → trả "" (passthrough, không áp dụng VFX).
        width, height: kích thước frame (dùng cho punch/shake).

    Trả về:
        Chuỗi filter ffmpeg (ví dụ: "drawtext=...,zoompan=...") hoặc "" nếu
        không có effect nào áp dụng.

    Raise:
        ValueError nếu bất kỳ annotation nào chứa 'setpts' (guard duration).
    """
    if not enabled or not annotations:
        return ""

    for ann in annotations:
        _check_setpts(ann)

    capped = annotations[:_MAX_BEATS_PER_SHOT]

    parts: list[str] = []
    for ann in capped:
        effect_type = ann.get("type", "")
        if "setpts" in str(effect_type).lower():
            raise ValueError(
                f"annotation type chứa 'setpts' → vi phạm duration-preserving. "
                f"Annotation: {ann}"
            )
        at: float = float(ann.get("at", 0.0))
        duration: float = float(ann.get("duration", 0.4))

        if effect_type == "pop":
            text = str(ann.get("text", ""))
            parts.append(_pop_filter(text, at, duration))
        elif effect_type == "punch":
            parts.append(_punch_filter(at, duration, width=width, height=height))
        elif effect_type == "shake":
            parts.append(_shake_filter(at, duration))
        elif effect_type == "emoji":
            emoji = str(ann.get("text", ""))
            parts.append(_emoji_filter(emoji, at, duration))

    return ",".join(parts)

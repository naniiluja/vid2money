"""Engine nhạc theo cảm xúc — phân tích mood và dựng music timeline.

Hai hàm công khai:
  resolve_mood(shot) → str         chọn mood cho 1 shot
  build_music_timeline(shots, durations) → list   gộp mood liền kề thành segments

Taxonomy 6 mood theo Russell valence-arousal (calm/uplifting/tense/somber/playful/triumphant)
cùng BPM/tonality và keyword để fallback khi shot.mood không hợp lệ.
Nguồn: EMOPIA, PsychologyFanatic, PMC tempo research.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from videopipe.storyboard import Shot

MOOD_TAXONOMY: dict[str, list[str]] = {
    "calm": [
        "calm", "peaceful", "serene", "relax", "quiet", "gentle", "slow",
        "tranquil", "bình yên", "thư thái", "nhẹ nhàng", "yên tĩnh",
    ],
    "uplifting": [
        "uplifting", "hope", "hopeful", "bright", "positive", "rise", "grow",
        "hy vọng", "tươi sáng", "phát triển", "nâng cao",
    ],
    "tense": [
        "tense", "tension", "danger", "crisis", "threat", "urgent", "fear",
        "conflict", "dramatic", "suspense",
        "khủng hoảng", "nguy hiểm", "căng thẳng", "đe dọa", "khẩn cấp",
        "sợ hãi", "xung đột",
    ],
    "somber": [
        "somber", "sad", "loss", "grief", "dark", "heavy", "mourn", "tragic",
        "melancholy", "sorrow",
        "buồn", "mất mát", "đau thương", "u ám", "tang thương",
    ],
    "playful": [
        "playful", "fun", "funny", "humor", "light", "joke", "amusing",
        "cheerful", "quirky", "silly",
        "vui nhộn", "hài hước", "vui vẻ", "tinh nghịch",
    ],
    "triumphant": [
        "triumphant", "triumph", "victory", "success", "win", "achieve",
        "celebrate", "proud", "conquer",
        "chiến thắng", "thành công", "vinh quang", "đỉnh cao",
    ],
}

_DEFAULT_MOOD = "calm"


def resolve_mood(shot: "Shot") -> str:
    """Xác định mood cho 1 shot.

    Ưu tiên theo thứ tự:
    1. shot.mood hợp lệ (có trong MOOD_TAXONOMY) → dùng trực tiếp.
    2. Fallback: phân tích keyword trong narration → chọn mood có nhiều keyword khớp nhất.
    3. Không khớp keyword nào → trả 'calm' (mặc định).

    Tham số:
        shot: Shot dataclass với field narration (str) và mood (str | None).

    Trả về:
        Một trong 6 key của MOOD_TAXONOMY.
    """
    mood_attr = getattr(shot, "mood", None)
    if mood_attr and mood_attr in MOOD_TAXONOMY:
        return mood_attr

    text = (shot.narration or "").lower().strip()
    if not text:
        return _DEFAULT_MOOD

    scores: dict[str, int] = {mood: 0 for mood in MOOD_TAXONOMY}
    for mood, keywords in MOOD_TAXONOMY.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[mood] += 1

    best_mood = max(scores, key=lambda m: scores[m])
    if scores[best_mood] == 0:
        return _DEFAULT_MOOD
    return best_mood


def build_music_timeline(
    shots: list["Shot"],
    durations: list[float],
) -> list[dict]:
    """Dựng music timeline từ danh sách shot và thời lượng tương ứng.

    Gộp các shot liền kề cùng mood thành 1 segment (để giảm số mối acrossfade).
    Điểm cắt (start/end) trùng ranh giới shot.

    Tham số:
        shots: danh sách Shot (đã có mood sau resolve_mood).
        durations: thời lượng (giây) tương ứng từng shot (cùng thứ tự).

    Trả về:
        list[dict] với mỗi phần tử gồm:
          - mood (str): tên mood
          - start (float): thời điểm bắt đầu trong video (giây)
          - duration (float): tổng thời lượng segment (giây)
    """
    if not shots:
        return []

    timeline: list[dict] = []
    running_start = 0.0

    for shot, dur in zip(shots, durations):
        mood = resolve_mood(shot)
        if timeline and timeline[-1]["mood"] == mood:
            timeline[-1]["duration"] += dur
        else:
            timeline.append({
                "mood": mood,
                "start": running_start,
                "duration": dur,
            })
        running_start += dur

    return timeline

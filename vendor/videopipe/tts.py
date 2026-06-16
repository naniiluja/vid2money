"""Bước [3] TTS — text → mp3 + srt bằng edge-tts.

Dùng edge_tts.Communicate stream để vừa ghi audio vừa thu boundary events,
rồi SubMaker.get_srt() xuất phụ đề khớp lời. Dùng SentenceBoundary cho phụ đề
video (mỗi cue 1 câu — dễ đọc hơn từng từ).

Lưu ý: edge-tts gọi dịch vụ Microsoft Edge TTS online → cần internet.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import aiohttp
import edge_tts

log = logging.getLogger("videopipe")

# Boundary dùng cho phụ đề. SentenceBoundary = mỗi cue một câu (dễ đọc trên video).
_SUBTITLE_BOUNDARY = "SentenceBoundary"

# Retry config: tối đa 3 lần, backoff 2^attempt giây (2s, 4s).
_TTS_MAX_RETRIES = 3
_TTS_BACKOFF_BASE = 2.0  # giây

# Các loại exception mạng/transient của edge-tts + aiohttp đáng retry.
# Lỗi không-transient (ValueError, edge_tts không nhận voice, v.v.) KHÔNG retry.
_TRANSIENT_EXCEPTIONS = (
    aiohttp.ClientConnectionError,   # bao gồm ServerDisconnectedError, ClientConnectorError...
    aiohttp.ServerTimeoutError,
    aiohttp.ClientPayloadError,
    TimeoutError,
    ConnectionError,
    OSError,  # socket-level errors
)


def _srt_last_end_seconds(srt_text: str) -> float:
    """Lấy thời điểm kết thúc của cue cuối (giây) từ nội dung SRT.

    Dòng timestamp dạng: 00:00:03,120 --> 00:00:07,480
    Trả về mốc kết thúc cuối cùng = thời lượng audio ước lượng từ SRT.
    """
    last_end = 0.0
    for line in srt_text.splitlines():
        if "-->" not in line:
            continue
        end = line.split("-->")[1].strip()
        hh, mm, rest = end.split(":")
        ss, ms = rest.split(",")
        seconds = int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
        last_end = max(last_end, seconds)
    return last_end


async def _synthesize_async(
    text: str, out_mp3: Path, out_srt: Path, voice: str, rate: str
) -> float:
    communicate = edge_tts.Communicate(
        text=text, voice=voice, rate=rate, boundary=_SUBTITLE_BOUNDARY
    )
    submaker = edge_tts.SubMaker()

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    with out_mp3.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)

    srt_text = submaker.get_srt()
    out_srt.write_text(srt_text, encoding="utf-8")
    return _srt_last_end_seconds(srt_text)


def synthesize(
    text: str,
    out_mp3: Path,
    out_srt: Path,
    voice: str = "en-US-GuyNeural",
    rate: str = "-8%",
) -> float:
    """Sinh mp3 + srt cho một đoạn text. Trả về thời lượng (giây) suy từ SRT.

    Thời lượng này là input cho bước ghép ffmpeg (số frame = dur * fps).

    Retry bounded (_TTS_MAX_RETRIES lần) CHỈ khi lỗi mạng/transient (_TRANSIENT_EXCEPTIONS).
    Lỗi không-transient (ValueError, lỗi nghiệp vụ) → raise ngay (fail-fast).
    rate được truyền qua MỌI lần thử — không bị reset về default khi retry.
    """
    if not text.strip():
        raise ValueError("text rỗng — không thể TTS")

    last_exc: Exception | None = None
    for attempt in range(1, _TTS_MAX_RETRIES + 1):
        try:
            duration = asyncio.run(_synthesize_async(text, out_mp3, out_srt, voice, rate))
            log.info(
                "TTS xong: %s (%.2fs) + %s", out_mp3.name, duration, out_srt.name
            )
            return duration
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _TTS_MAX_RETRIES:
                wait = _TTS_BACKOFF_BASE ** (attempt - 1)
                log.warning(
                    "TTS lần %d/%d thất bại (%s: %s) — retry sau %.0fs",
                    attempt, _TTS_MAX_RETRIES, type(exc).__name__, exc, wait,
                )
                time.sleep(wait)
            else:
                log.warning(
                    "TTS lần %d/%d thất bại (%s: %s) — hết lượt retry, raise",
                    attempt, _TTS_MAX_RETRIES, type(exc).__name__, exc,
                )
        # Lỗi không phải _TRANSIENT_EXCEPTIONS → không bắt → raise ngay (fail-fast)

    # Hết retry → raise lỗi cuối (không nuốt)
    raise last_exc  # type: ignore[misc]

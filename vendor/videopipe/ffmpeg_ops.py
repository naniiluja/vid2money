"""Bước [5] segments + [6] assemble — ghép ảnh tĩnh + audio + sub thành MP4.

make_segment: 1 ảnh + thời lượng → 1 clip mp4 có hiệu ứng Ken Burns (zoompan).
assemble:     nối các segment + mux audio + burn phụ đề SRT → final.mp4.

Output chuẩn YouTube: libx264, yuv420p, +faststart.
Đã verify trên máy: ffmpeg 8.0.1 essentials build CÓ libass (filter subtitles/ass).
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("videopipe")

# Font mặc định (tên) dùng trong filter subtitles.
_DEFAULT_FONT_NAME = "Segoe UI"

# Thư mục font hệ thống theo platform — chỉ dùng nếu assets/fonts/ không có .ttf.
_SYSTEM_FONTS_BY_PLATFORM: dict[str, Path] = {
    "Windows": Path("C:/Windows/Fonts"),
    "Darwin": Path("/System/Library/Fonts"),
    "Linux": Path("/usr/share/fonts"),
}


def _check_tools() -> None:
    """Kiểm tra ffmpeg + ffprobe có trong PATH; raise RuntimeError nếu thiếu.

    Gọi sớm để lỗi rõ ràng thay vì crash mơ hồ ở giữa pipeline.
    """
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"Không tìm thấy '{tool}' trong PATH.\n"
                "Cài đặt: https://ffmpeg.org/download.html rồi thêm vào PATH.\n"
                "Windows: winget install ffmpeg  hoặc  choco install ffmpeg"
            )


def _resolve_fonts_dir() -> Path | None:
    """Tìm thư mục font theo thứ tự ưu tiên, trả None nếu không tìm thấy.

    Thứ tự:
    1. assets/fonts/ của repo — nếu có ít nhất 1 file .ttf.
    2. Font hệ thống theo platform (Windows/macOS/Linux).
    3. Không thấy → trả None (subtitles vẫn chạy với font mặc định libass).
    """
    from videopipe.config import ASSETS_ROOT  # import cục bộ tránh circular

    # 1. Font trong repo (portable nhất).
    repo_fonts = ASSETS_ROOT / "fonts"
    if repo_fonts.is_dir() and any(repo_fonts.glob("*.ttf")):
        log.debug("fonts_dir resolve từ repo assets: %s", repo_fonts)
        return repo_fonts

    # 2. Font hệ thống theo platform hiện tại.
    sys_fonts = _SYSTEM_FONTS_BY_PLATFORM.get(platform.system())
    if sys_fonts and sys_fonts.is_dir():
        log.debug("fonts_dir resolve từ hệ thống (%s): %s", platform.system(), sys_fonts)
        return sys_fonts

    # 3. Không thấy — dùng font mặc định của libass (không đặt fontsdir).
    log.info(
        "Không tìm thấy thư mục font (assets/fonts/ hoặc hệ thống) — "
        "subtitles sẽ dùng font mặc định libass."
    )
    return None


def _run(cmd: list[str], timeout_s: int = 600) -> None:
    """Chạy ffmpeg, raise nếu lỗi hoặc timeout (kèm stderr để dễ debug).

    timeout_s: giới hạn thời gian subprocess (giây). Mặc định 600s cho encode dài.
    Khi quá hạn → subprocess.TimeoutExpired bắt và wrap thành RuntimeError rõ.
    """
    _check_tools()
    log.debug("ffmpeg: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ffmpeg timeout sau {timeout_s}s — lệnh bị hủy: {' '.join(cmd[:4])}..."
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi (exit {proc.returncode}):\n{proc.stderr[-2000:]}")


def probe_duration(media: Path, timeout_s: int = 60) -> float:
    """Đọc thời lượng (giây) của file media bằng ffprobe.

    timeout_s: giới hạn thời gian probe (giây). Mặc định 60s — đủ cho file lớn.
    """
    _check_tools()
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(media),
            ],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"ffprobe timeout sau {timeout_s}s khi probe: {media.name}"
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe lỗi: {proc.stderr}")
    return float(proc.stdout.strip())


def assert_duration_match(
    seg_dur: float, audio_dur: float, fps: int, tol_frames: int = 1
) -> None:
    """Kiểm tra thời lượng segment khớp audio trong phạm vi tol_frames frame.

    seg_dur: thời lượng video segment (giây).
    audio_dur: thời lượng audio (giây).
    fps: frame rate để đổi frame → giây.
    tol_frames: số frame dung sai (mặc định 1 frame — làm tròn ffmpeg là bình thường).

    Lệch ≤ tol_frames/fps → không raise (làm tròn frame là expected).
    Lệch > tol_frames/fps → raise ValueError rõ (desync đáng kể).
    """
    # Epsilon nhỏ (0.5ms) bù sai số float khi tính 1/fps — timestamps media không cần chính xác hơn 1ms.
    _FLOAT_EPS = 0.0005
    tol_s = tol_frames / fps + _FLOAT_EPS
    diff = abs(seg_dur - audio_dur)
    if diff > tol_s:
        log.warning(
            "desync: seg=%.4fs audio=%.4fs diff=%.4fs > tol %.4fs (%d frame @ %dfps)",
            seg_dur, audio_dur, diff, tol_s, tol_frames, fps,
        )
        raise ValueError(
            f"desync: segment {seg_dur:.4f}s vs audio {audio_dur:.4f}s "
            f"(diff={diff:.4f}s > {tol_frames}/{fps}fps = {tol_s:.4f}s)"
        )


def _temp_path(out: Path) -> Path:
    """Trả về đường dẫn file tạm bên cạnh file đích, giữ nguyên extension.

    Ví dụ: seg_0.mp4 → seg_0.partial.mp4 (extension giữ nguyên để ffmpeg biết format).
    Pattern: <stem>.partial<suffix> — stem chứa '.partial' để phân biệt, suffix = ext gốc.
    """
    return out.with_name(out.stem + ".partial" + out.suffix)


def _finalize(tmp: Path, out: Path) -> None:
    """Rename file tạm sang đích (atomic trên Windows dùng os.replace).

    os.replace ghi đè nếu đích đã tồn tại — an toàn trên Windows.
    """
    os.replace(str(tmp), str(out))


def make_segment(
    image: Path,
    audio_dur: float,
    out_seg: Path,
    fps: int,
    width: int,
    height: int,
    vfx_annotations: list[dict] | None = None,
    vfx_enabled: bool = False,
) -> Path:
    """Tạo 1 video segment từ ảnh tĩnh với Ken Burns, thời lượng = audio_dur.

    zoompan: zoom chậm 1.0 → 1.12 trong suốt segment. d = số frame = dur * fps.
    Scale ảnh trước để đủ độ phân giải cho zoompan crop mượt.

    vfx_annotations: danh sách beat VFX của shot (từ storyboard.Shot.vfx).
    vfx_enabled: True → nối filter VFX vào chuỗi -vf (duration-preserving).

    Pattern: ffmpeg ghi vào .partial trước; chỉ rename sang đích khi thành công.
    Nếu _run raise → xoá .partial trước khi re-raise → resume không thấy artifact cụt.
    """
    from videopipe.vfx import build_vfx_filters  # import cục bộ tránh circular

    n_frames = max(1, round(audio_dur * fps))
    zoom_expr = "min(zoom+0.0009,1.12)"
    vf = (
        f"scale={width*2}:{height*2},"
        f"zoompan=z='{zoom_expr}':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={n_frames}:s={width}x{height}:fps={fps},"
        f"setsar=1"
    )

    vfx_str = build_vfx_filters(
        vfx_annotations or [], enabled=vfx_enabled, width=width, height=height
    )
    if vfx_str:
        vf = f"{vf},{vfx_str}"

    out_seg.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(out_seg)
    try:
        _run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(image),
            "-vf", vf, "-t", f"{audio_dur:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_seg)
    log.info("Segment: %s (%.2fs, %d frames)", out_seg.name, audio_dur, n_frames)
    return out_seg


def make_multi_image_segment(
    images_list: list[Path], audio_dur: float, out_seg: Path,
    fps: int, width: int, height: int,
) -> Path:
    """Tạo 1 segment từ NHIỀU ảnh, chia đều audio_dur cho từng ảnh (mỗi ảnh Ken Burns).

    Dùng cho shot có images>1: đổi ảnh giữa chừng mà vẫn khớp 1 đoạn narration.
    """
    if len(images_list) == 1:
        return make_segment(images_list[0], audio_dur, out_seg, fps, width, height)

    per = audio_dur / len(images_list)
    parts: list[Path] = []
    for k, img in enumerate(images_list):
        part = out_seg.with_name(f"{out_seg.stem}_p{k}.mp4")
        make_segment(img, per, part, fps, width, height)
        parts.append(part)

    # Nối các part bằng concat demuxer (cùng codec/res).
    list_file = out_seg.with_suffix(".parts.txt")
    list_file.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8"
    )
    tmp = _temp_path(out_seg)
    try:
        _run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        list_file.unlink(missing_ok=True)
        for p in parts:
            p.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_seg)
    list_file.unlink(missing_ok=True)
    for p in parts:
        p.unlink(missing_ok=True)
    log.info("Segment (multi %d ảnh): %s (%.2fs)", len(images_list), out_seg.name, audio_dur)
    return out_seg


def make_color_placeholder(out_image: Path, width: int, height: int, color: str = "#15202b") -> Path:
    """Tạo ảnh PNG màu trơn làm placeholder (dùng cho Task 003 trước khi có ảnh thật)."""
    out_image.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d=1",
        "-frames:v", "1", str(out_image),
    ])
    return out_image


def _escape_subtitles_path(srt: Path) -> str:
    """Escape path SRT cho filter subtitles trên Windows.

    libass filter syntax: dấu \\ → /, dấu : sau ổ đĩa → \\: , và bọc trong ''.
    """
    p = str(srt).replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


def _escape_drawtext(text: str) -> str:
    """Escape chuỗi cho ffmpeg drawtext filter (dấu : và ' cần escape).

    drawtext yêu cầu: dấu ' → \\'', dấu : → \\:, dấu \\ → \\\\.
    """
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def make_title_card(
    title: str,
    dur: float,
    out_seg: Path,
    fps: int,
    width: int,
    height: int,
    bg_color: str = "#FAF7F0",
    fonts_dir: Path | None = None,
    font_name: str = _DEFAULT_FONT_NAME,
) -> Path:
    """Tạo title card (nền màu + chữ tiêu đề căn giữa, fade-in).

    Card cùng codec/res/pix_fmt với make_segment để concat filter không lỗi.
    Dùng lavfi color source → drawtext → fade → libx264 yuv420p.

    Nếu fonts_dir có file .ttf tên khớp font_name (hoặc bất kỳ .ttf đầu tiên),
    dùng fontfile= để chắc chắn; ngược lại để drawtext tự resolve.
    """
    out_seg.parent.mkdir(parents=True, exist_ok=True)

    # Tìm fontfile cụ thể nếu có fonts_dir (portable, không hardcode path).
    fontfile_arg = ""
    if fonts_dir is not None and fonts_dir.is_dir():
        # Ưu tiên file .ttf có tên chứa font_name (case-insensitive).
        candidates = list(fonts_dir.glob("*.ttf"))
        if candidates:
            matched = [f for f in candidates if font_name.lower() in f.stem.lower()]
            chosen = matched[0] if matched else candidates[0]
            # Escape path cho drawtext: \\ → /, : → \\:
            fp = chosen.as_posix().replace(":", "\\:")
            fontfile_arg = f":fontfile='{fp}'"

    escaped_title = _escape_drawtext(title)
    # drawtext: vẽ chữ căn giữa, màu tối trên nền sáng off-white (người que style).
    drawtext = (
        f"drawtext=text='{escaped_title}'"
        f"{fontfile_arg}"
        f":fontsize=72:fontcolor=#1A1A2E"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":line_spacing=10"
    )
    # fade=in 0.8s ngay đầu card (khoảng thở nhẹ nhàng).
    vf = f"{drawtext},fade=t=in:st=0:d=0.8,setsar=1"

    tmp = _temp_path(out_seg)
    try:
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={bg_color}:s={width}x{height}:d={dur:.3f}",
            "-vf", vf,
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_seg)
    log.info("Title card: %s (%.2fs)", out_seg.name, dur)
    return out_seg


def make_end_card(
    outro_text: str,
    dur: float,
    out_seg: Path,
    fps: int,
    width: int,
    height: int,
    bg_color: str = "#FAF7F0",
    fonts_dir: Path | None = None,
    font_name: str = _DEFAULT_FONT_NAME,
) -> Path:
    """Tạo end card (nền màu, fade-out; tùy chọn có chữ nếu outro_text không rỗng).

    Card cùng codec/res/pix_fmt với make_segment để concat filter không lỗi.
    fade-out bắt đầu từ 0.5s trước khi kết thúc để mượt mà.
    """
    out_seg.parent.mkdir(parents=True, exist_ok=True)

    # Tìm fontfile nếu có fonts_dir.
    fontfile_arg = ""
    if fonts_dir is not None and fonts_dir.is_dir():
        candidates = list(fonts_dir.glob("*.ttf"))
        if candidates:
            matched = [f for f in candidates if font_name.lower() in f.stem.lower()]
            chosen = matched[0] if matched else candidates[0]
            fp = chosen.as_posix().replace(":", "\\:")
            fontfile_arg = f":fontfile='{fp}'"

    # fade-out bắt đầu 1.0s trước khi hết card.
    fade_start = max(0.0, dur - 1.0)
    fade_filter = f"fade=t=out:st={fade_start:.3f}:d=1.0"

    if outro_text:
        escaped = _escape_drawtext(outro_text)
        drawtext = (
            f"drawtext=text='{escaped}'"
            f"{fontfile_arg}"
            f":fontsize=60:fontcolor=#1A1A2E"
            f":x=(w-text_w)/2:y=(h-text_h)/2"
            f":line_spacing=10"
        )
        vf = f"{drawtext},{fade_filter},setsar=1"
    else:
        # Không có chữ — chỉ nền + fade-out (khoảng thở thuần).
        vf = f"{fade_filter},setsar=1"

    tmp = _temp_path(out_seg)
    try:
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={bg_color}:s={width}x{height}:d={dur:.3f}",
            "-vf", vf,
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_seg)
    log.info("End card: %s (%.2fs)", out_seg.name, dur)
    return out_seg


def make_silent_audio(dur: float, out_audio: Path) -> Path:
    """Tạo đoạn audio im lặng dài dur giây (dùng cho intro/outro card).

    anullsrc → aac → file mp3/mp4. Dùng để chèn khoảng lặng vào full_audio
    tương ứng với title card và end card (không có giọng đọc trong card).

    Pattern temp-rename: ghi .partial trước, rename sang đích khi thành công.
    """
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(out_audio)
    try:
        _run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", f"{dur:.3f}",
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_audio)
    log.debug("Silent audio: %s (%.2fs)", out_audio.name, dur)
    return out_audio


def mix_background_music(
    video_in: Path, music: Path, out_video: Path, duck_db: float = 16.0
) -> Path:
    """Trộn nhạc nền vào video đã có giọng đọc.

    - Nhạc được giảm `duck_db` dB so với giọng (16-18 dB = sweet spot, WCAG >=20 dB).
    - Nhạc loop nếu ngắn hơn video, fade in 1.5s / fade out 2.5s, cắt theo độ dài video.
    - amix với duration=first (giữ độ dài video), giữ nguyên stream video.
    Theo nghiên cứu tâm lý âm nhạc: instrumental, ~75-85 BPM, nền dưới giọng ~16-18 dB.
    """
    vdur = probe_duration(video_in)
    gain = 10 ** (-duck_db / 20.0)  # đổi dB sang hệ số biên độ tuyến tính
    out_video.parent.mkdir(parents=True, exist_ok=True)
    # [1:a] nhạc: loop vô hạn (stream_loop) rồi cắt; hạ volume; fade.
    filter_complex = (
        f"[1:a]volume={gain:.4f},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={max(0.0, vdur - 2.5):.2f}:d=2.5[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    tmp = _temp_path(out_video)
    try:
        _run([
            "ffmpeg", "-y",
            "-i", str(video_in),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{vdur:.3f}",
            "-movflags", "+faststart",
            str(tmp),
        ])
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_video)
    log.info("Nhạc nền: %s (giảm %.0f dB) → %s", music.name, duck_db, out_video.name)
    return out_video


def mix_emotion_tracks(
    timeline: list[dict],
    mood_files: dict[str, "Path"],
    out_audio: Path,
    crossfade_d: float = 2.0,
) -> Path:
    """Nối nhiều track nhạc theo music timeline với acrossfade giữa các segment.

    Mỗi segment trong timeline được cắt (atrim) đúng thời lượng từ track nhạc tương ứng
    rồi nối lại bằng acrossfade(d=crossfade_d, c1=exp, c2=exp).

    Công thức duration output:
      Σ(dur_segment) − (n_joins × crossfade_d)
    với n_joins = len(timeline) − 1.

    Tham số:
        timeline: list[dict] từ build_music_timeline, mỗi phần tử có mood + duration.
        mood_files: ánh xạ mood → Path file nhạc nguồn.
        out_audio: đường dẫn file output mp3.
        crossfade_d: thời gian crossfade (giây, mặc định 2.0).

    Fallback: nếu mood không có trong mood_files, dùng mood đầu tiên có sẵn.
    Nếu timeline rỗng → raise ValueError.
    """
    from pathlib import Path as _Path

    if not timeline:
        raise ValueError("timeline rỗng — không có segment nhạc để mix")

    available_moods = list(mood_files.keys())
    if not available_moods:
        raise ValueError("mood_files rỗng — không có track nhạc nào")

    out_audio.parent.mkdir(parents=True, exist_ok=True)

    # Trường hợp chỉ 1 segment: atrim rồi xuất thẳng, không cần acrossfade.
    if len(timeline) == 1:
        seg = timeline[0]
        mood = seg["mood"]
        src = mood_files.get(mood) or mood_files[available_moods[0]]
        dur = seg["duration"]
        tmp = _temp_path(out_audio)
        try:
            _run([
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", str(src),
                "-t", f"{dur:.3f}",
                "-af", "afade=t=out:st={:.3f}:d={:.3f}".format(
                    max(0.0, dur - crossfade_d), crossfade_d
                ),
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(tmp),
            ])
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        _finalize(tmp, out_audio)
        log.info("Emotion mix (1 segment): %s (%.2fs)", out_audio.name, dur)
        return out_audio

    # Nhiều segment: dựng filter_complex với acrossfade nối tiếp.
    # Mỗi segment: [N:a]atrim=duration=DUR,asetpts=expr → [segN]
    # Nối: [seg0][seg1]acrossfade=d=D:c1=exp:c2=exp[ac01];
    #        [ac01][seg2]acrossfade=d=D:c1=exp:c2=exp[ac012]; ...
    cmd: list[str] = ["ffmpeg", "-y"]

    for i, seg in enumerate(timeline):
        mood = seg["mood"]
        src = mood_files.get(mood) or mood_files[available_moods[0]]
        cmd += ["-stream_loop", "-1", "-i", str(src)]

    filter_parts: list[str] = []
    for i, seg in enumerate(timeline):
        dur = seg["duration"]
        # atrim bảo đảm độ dài chính xác; asetpts reset timestamps sau trim.
        filter_parts.append(
            f"[{i}:a]atrim=duration={dur:.3f},asetpts=PTS-STARTPTS[s{i}]"
        )

    # Nối acrossfade từng cặp: [s0][s1] → [ac1], [ac1][s2] → [ac2], ...
    n = len(timeline)
    # Cặp đầu tiên
    filter_parts.append(
        f"[s0][s1]acrossfade=d={crossfade_d:.3f}:c1=exp:c2=exp[ac1]"
    )
    for i in range(2, n):
        prev_label = f"ac{i - 1}"
        curr_label = f"ac{i}"
        filter_parts.append(
            f"[{prev_label}][s{i}]acrossfade=d={crossfade_d:.3f}:c1=exp:c2=exp[{curr_label}]"
        )

    final_label = f"ac{n - 1}"
    filter_complex = ";".join(filter_parts)

    tmp = _temp_path(out_audio)
    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"[{final_label}]",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(tmp),
    ]
    try:
        _run(cmd)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_audio)
    log.info(
        "Emotion mix (%d segment, %d crossfade): %s",
        n, n - 1, out_audio.name,
    )
    return out_audio


def assemble(
    segments: list[Path],
    full_audio: Path,
    srt: Path,
    out_final: Path,
    fps: int,
    fonts_dir: Path | None = None,
    font_name: str = _DEFAULT_FONT_NAME,
) -> Path:
    """Nối segments + mux audio + burn phụ đề → final.mp4 chuẩn YouTube.

    1 lệnh ffmpeg duy nhất: concat filter (video) → subtitles (burn) → mux audio.
    Dùng concat filter (không phải demuxer) để chắc chắn đồng nhất format.

    fonts_dir=None → resolve động (repo assets/fonts/ → hệ thống → bỏ qua fontsdir,
    subtitles vẫn chạy với font mặc định libass).
    """
    if not segments:
        raise ValueError("Không có segment để ghép")

    # Resolve fonts_dir nếu chưa truyền vào (portable trên mọi máy).
    if fonts_dir is None:
        fonts_dir = _resolve_fonts_dir()

    out_final.parent.mkdir(parents=True, exist_ok=True)
    srt_arg = _escape_subtitles_path(srt)
    style = (
        f"FontName={font_name},Fontsize=22,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=40"
    )

    # Input: từng segment + audio tổng.
    cmd: list[str] = ["ffmpeg", "-y"]
    for seg in segments:
        cmd += ["-i", str(seg)]
    cmd += ["-i", str(full_audio)]

    n = len(segments)
    concat_inputs = "".join(f"[{i}:v:0]" for i in range(n))

    # Thêm fontsdir vào filter chỉ khi có thư mục font thực (portable).
    if fonts_dir is not None:
        fonts_arg = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
        sub_filter = f"[v]subtitles='{srt_arg}':fontsdir='{fonts_arg}':force_style='{style}'[vout]"
    else:
        # Không có fontsdir → libass dùng font mặc định hệ thống.
        sub_filter = f"[v]subtitles='{srt_arg}':force_style='{style}'[vout]"

    filter_complex = (
        f"{concat_inputs}concat=n={n}:v=1:a=0[v];"
        f"{sub_filter}"
    )
    tmp = _temp_path(out_final)
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{n}:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        _run(cmd)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _finalize(tmp, out_final)
    log.info("Final: %s", out_final)
    return out_final

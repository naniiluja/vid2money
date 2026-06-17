"""Orchestrator — nối tuần tự các bước của pipeline.

Luồng đầy đủ (Task 005):
  [2] script    → script_gen.generate_script  → script.json (nhiều scene)
      style     → images.generate_image        → style_sheet.png (reference)
  loop mỗi scene:
    [3] tts     → tts.synthesize               → scene_N.mp3 + scene_N.srt
    [4] images  → images.generate_image(ref)   → scene_N.png
    [5] segment → ffmpeg_ops.make_segment       → seg_N.mp4
  [6] assemble  → ffmpeg_ops.assemble (gộp SRT) → final.mp4

[1] research (Task 006) sẽ chèn TRƯỚC bước script để chọn topic tự động.
"""

from __future__ import annotations

import logging
from pathlib import Path

from videopipe import ffmpeg_ops, images, research, script_gen, tts
from videopipe.config import PipelineConfig, is_duration_off
from videopipe.storyboard import Storyboard

log = logging.getLogger("videopipe")


def _merge_srt(scene_srts: list[tuple[Path, float]], out_srt: Path) -> None:
    """Gộp các SRT từng scene thành 1 SRT toàn video, cộng dồn offset thời gian.

    scene_srts: list (đường dẫn srt, offset_giây_bắt_đầu_của_scene).
    """
    def fmt(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def parse_ts(ts: str) -> float:
        hh, mm, rest = ts.split(":")
        ss, msec = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(msec) / 1000.0

    lines_out: list[str] = []
    idx = 1
    for srt_path, offset in scene_srts:
        blocks = srt_path.read_text(encoding="utf-8").strip().split("\n\n")
        for block in blocks:
            rows = block.splitlines()
            if len(rows) < 2 or "-->" not in rows[1]:
                continue
            start, end = (p.strip() for p in rows[1].split("-->"))
            new_start = fmt(parse_ts(start) + offset)
            new_end = fmt(parse_ts(end) + offset)
            text = "\n".join(rows[2:])
            lines_out.append(f"{idx}\n{new_start} --> {new_end}\n{text}\n")
            idx += 1
    out_srt.write_text("\n".join(lines_out), encoding="utf-8")


def _apply_srt_offset(srt_content: str, offset_seconds: float) -> str:
    """Cộng offset_seconds vào mọi timestamp trong nội dung SRT, trả chuỗi mới.

    Hàm thuần (pure) — không đọc/ghi file, dễ unit test.
    Dùng khi có title card ở đầu: mọi SRT của shot phải cộng intro_seconds
    để subtitle khớp giọng đọc (vì video dài hơn do card chèn trước).

    DESYNC NOTE: đây là điểm dễ sai nhất — offset phải bằng ĐÚNG thời lượng
    card (không phải approximate). Test coverage bắt buộc.
    """
    def fmt_ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def parse_ts(ts: str) -> float:
        hh, mm, rest = ts.split(":")
        ss, msec = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(msec) / 1000.0

    if not srt_content.strip():
        return srt_content

    lines_out: list[str] = []
    idx = 1
    blocks = srt_content.strip().split("\n\n")
    for block in blocks:
        rows = block.splitlines()
        if len(rows) < 2 or "-->" not in rows[1]:
            continue
        start_str, end_str = (p.strip() for p in rows[1].split("-->"))
        new_start = fmt_ts(parse_ts(start_str) + offset_seconds)
        new_end = fmt_ts(parse_ts(end_str) + offset_seconds)
        text = "\n".join(rows[2:])
        lines_out.append(f"{idx}\n{new_start} --> {new_end}\n{text}\n")
        idx += 1
    return "\n".join(lines_out)


def run(
    config: PipelineConfig,
    topic_override: str | None = None,
    n_scenes: int = 4,
    from_trending: bool = False,
) -> Path:
    """Chạy pipeline đầy đủ multi-scene. Trả về đường dẫn final.mp4."""
    config.ensure_dirs()
    log.info("Run dir sẵn sàng: %s", config.work_dir)

    topic = topic_override or config.topic
    evidence = ""

    # [1] research — (tùy chọn) tìm chủ đề trending từ seed.
    if from_trending:
        result = research.find_trending(topic, save_dir=config.work_dir)
        topic, evidence = result.title, result.evidence
        log.info("[1] research  — topic: %s", topic)

    # [2] script — sinh kịch bản nhiều scene.
    doc = script_gen.generate_script(
        topic=topic,
        out_path=config.script_path,
        n_scenes=n_scenes,
        style_anchor=config.style.image_style_anchor,
        evidence=evidence,
    )
    log.info("[2] script    — %d scene", len(doc.scenes))

    # style sheet — gen TRƯỚC, dùng làm reference image cho mọi scene → nhất quán.
    style_sheet = config.work_dir / "style_sheet.png"
    images.generate_image(
        prompt=doc.character_sheet_prompt,
        out_path=style_sheet,
        style=config.style,
        backend=config.image_backend,
    )
    log.info("style sheet   — %s", style_sheet.name)

    # loop scenes: tts + image(ref=style_sheet) + segment.
    segments: list[Path] = []
    scene_srts: list[tuple[Path, float]] = []
    running_offset = 0.0
    for scene in doc.scenes:
        i = scene.id
        dur = tts.synthesize(
            text=scene.narration,
            out_mp3=config.scene_audio(i),
            out_srt=config.scene_srt(i),
            voice=config.voice,
            rate=config.tts_rate,
        )
        audio_dur = ffmpeg_ops.probe_duration(config.scene_audio(i))
        images.generate_image(
            prompt=scene.image_prompt,
            out_path=config.scene_image(i),
            style=config.style,
            ref_image=style_sheet,
            backend=config.image_backend,
        )
        seg = ffmpeg_ops.make_segment(
            config.scene_image(i), audio_dur, config.scene_segment(i),
            config.fps, config.width, config.height,
        )
        segments.append(seg)
        scene_srts.append((config.scene_srt(i), running_offset))
        running_offset += audio_dur
        log.info("[3-5] scene %d xong (%.2fs)", i, audio_dur)

    # gộp audio các scene thành 1 file + gộp SRT (cộng offset).
    full_audio = config.work_dir / "full_audio.mp3"
    _concat_audio([config.scene_audio(s.id) for s in doc.scenes], full_audio)
    merged_srt = config.work_dir / "full.srt"
    _merge_srt(scene_srts, merged_srt)

    # [6] assemble.
    assemble_kwargs = {}
    if config.fonts_dir.exists() and any(config.fonts_dir.glob("*.ttf")):
        assemble_kwargs["fonts_dir"] = config.fonts_dir
    ffmpeg_ops.assemble(
        segments=segments,
        full_audio=full_audio,
        srt=merged_srt,
        out_final=config.final_path,
        fps=config.fps,
        **assemble_kwargs,
    )
    log.info("[6] assemble  — %s", config.final_path)

    if config.target_minutes is not None:
        actual_s = ffmpeg_ops.probe_duration(config.final_path)
        target_s = config.target_minutes * 60
        if is_duration_off(actual_s, target_s):
            log.warning(
                "Thời lượng thực tế %.1fs lệch khỏi mục tiêu %.1fs (%.0f%%) — "
                "điều chỉnh số shot hoặc narration để bám --target-minutes %.1f.",
                actual_s,
                target_s,
                abs(actual_s / target_s - 1) * 100,
                config.target_minutes,
            )

    log.info("Pipeline hoàn tất. Final: %s", config.final_path)
    return config.final_path


def _concat_audio(audios: list[Path], out_audio: Path) -> None:
    """Nối các mp3 scene thành 1 file (concat demuxer)."""
    list_file = out_audio.parent / "_audio_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in audios), encoding="utf-8"
    )
    ffmpeg_ops._run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(out_audio),
    ])
    list_file.unlink(missing_ok=True)


def run_storyboard(config: PipelineConfig, board: Storyboard) -> Path:
    """Dựng video DÀI từ storyboard (Claude tự viết). Resume-friendly.

    Mỗi shot: tts (skip nếu có) + gen N ảnh (skip nếu có) + multi-image segment.
    Chạy lại pipeline → bỏ qua mọi artifact đã tồn tại → tiếp tục từ chỗ dở.

    Nếu show_title_card=True:
      - title card (~intro_seconds) được chèn đầu danh sách segment.
      - end card (~outro_seconds) được chèn cuối danh sách segment.
      - Toàn bộ SRT của shot được cộng thêm intro_seconds (offset) để khớp
        vị trí giọng đọc trong video sau khi có card ở đầu.
      - Audio: silent mp3 intro + concat shot audios + silent mp3 outro để
        tổng thời lượng audio = tổng video (card + shots + card).
    """
    config.ensure_dirs()
    log.info("Storyboard: %s — %d shot, %d ảnh", board.title, len(board.shots), board.total_images)

    # Resolve fonts_dir một lần để dùng chung cho cả card + assemble.
    fonts_dir = ffmpeg_ops._resolve_fonts_dir()

    # style sheet reference (resume).
    style_sheet = config.work_dir / "style_sheet.png"
    images.generate_image(
        prompt=board.character_sheet_prompt, out_path=style_sheet, style=config.style,
        backend=config.image_backend,
    )

    segments: list[Path] = []
    scene_srts: list[tuple[Path, float]] = []
    shot_audios: list[Path] = []

    # offset bắt đầu từ intro_seconds nếu có card — sub của shot phải bù intro.
    srt_offset = config.intro_seconds if config.show_title_card else 0.0
    running_offset = srt_offset  # offset tích lũy cho từng shot (cộng thêm intro)

    for shot in board.shots:
        i = shot.id
        # [3] TTS (skip nếu đã có mp3 + srt).
        if not (config.scene_audio(i).exists() and config.scene_srt(i).exists()):
            tts.synthesize(
                shot.narration, config.scene_audio(i), config.scene_srt(i),
                voice=config.voice, rate=config.tts_rate,
            )
        audio_dur = ffmpeg_ops.probe_duration(config.scene_audio(i))

        # [4] gen N ảnh cho shot (mỗi ảnh resume riêng).
        n_img = max(1, shot.images)
        shot_imgs: list[Path] = []
        for k in range(n_img):
            img_path = config.shot_image(i, k)
            variant = shot.image_prompt
            if n_img > 1:
                variant = f"{shot.image_prompt} (moment {k + 1} of {n_img}, slight progression)"
            images.generate_image(
                prompt=variant, out_path=img_path,
                style=config.style, ref_image=style_sheet,
                backend=config.image_backend,
            )
            shot_imgs.append(img_path)

        # [5] segment (skip nếu đã có).
        seg = config.scene_segment(i)
        if not seg.exists():
            ffmpeg_ops.make_multi_image_segment(
                shot_imgs, audio_dur, seg, config.fps, config.width, config.height
            )
        segments.append(seg)

        # Desync check: probe segment và so với audio_dur (±1 frame dung sai làm tròn).
        # Lệch nhỏ (≤1 frame) → bình thường (ffmpeg làm tròn frame). Lệch lớn → log warning.
        # Không raise ở đây — lệch nhỏ do codec rounding sẽ không ảnh hưởng sync rõ rệt;
        # lệch lớn (>1 frame) đã log warning đủ để debug (hành vi quan sát được).
        seg_dur = ffmpeg_ops.probe_duration(seg)
        try:
            ffmpeg_ops.assert_duration_match(seg_dur, audio_dur, fps=config.fps)
        except ValueError as e:
            log.warning("shot %d/%d desync (tiếp tục): %s", i + 1, len(board.shots), e)

        # SRT offset tích lũy: intro_seconds (nếu có card) + thời lượng các shot trước.
        scene_srts.append((config.scene_srt(i), running_offset))
        shot_audios.append(config.scene_audio(i))
        running_offset += audio_dur
        log.info("shot %d/%d xong (%.2fs, %d ảnh)", i + 1, len(board.shots), audio_dur, n_img)

    # --- Chèn title card + end card nếu bật ---
    if config.show_title_card:
        title_seg = config.work_dir / "seg_title.mp4"
        end_seg = config.work_dir / "seg_end.mp4"

        # Luôn tạo lại card (nhỏ/nhanh, không cần resume).
        ffmpeg_ops.make_title_card(
            title=board.title,
            dur=config.intro_seconds,
            out_seg=title_seg,
            fps=config.fps,
            width=config.width,
            height=config.height,
            fonts_dir=fonts_dir,
        )
        ffmpeg_ops.make_end_card(
            outro_text=config.outro_text,
            dur=config.outro_seconds,
            out_seg=end_seg,
            fps=config.fps,
            width=config.width,
            height=config.height,
            fonts_dir=fonts_dir,
        )

        # Danh sách segment cuối: title + shots + end.
        all_segments = [title_seg] + segments + [end_seg]

        # Audio: silent_intro + concat shots + silent_outro.
        # Dùng 3 file riêng rồi concat để audio khớp chính xác tổng video.
        silent_intro = config.work_dir / "_silent_intro.mp3"
        silent_outro = config.work_dir / "_silent_outro.mp3"
        ffmpeg_ops.make_silent_audio(config.intro_seconds, silent_intro)
        ffmpeg_ops.make_silent_audio(config.outro_seconds, silent_outro)

        full_audio = config.work_dir / "full_audio.mp3"
        _concat_audio([silent_intro, *shot_audios, silent_outro], full_audio)
        log.info(
            "Card bật: intro=%.1fs + outro=%.1fs → total audio = intro + shots + outro",
            config.intro_seconds, config.outro_seconds,
        )
    else:
        # Bật/tắt: khi tắt card → hành vi cũ hoàn toàn (không offset SRT).
        all_segments = segments
        full_audio = config.work_dir / "full_audio.mp3"
        _concat_audio(shot_audios, full_audio)

    # gộp SRT — với offset đã tính từ intro_seconds (hoặc 0 nếu tắt card).
    merged_srt = config.work_dir / "full.srt"
    _merge_srt(scene_srts, merged_srt)

    assemble_kwargs: dict = {}
    if fonts_dir is not None:
        assemble_kwargs["fonts_dir"] = fonts_dir
    ffmpeg_ops.assemble(
        segments=all_segments, full_audio=full_audio, srt=merged_srt,
        out_final=config.final_path, fps=config.fps, **assemble_kwargs,
    )

    # nhạc nền (tùy chọn): static (hành vi cũ) hoặc emotion (đổi track theo mood).
    if getattr(config, "music_mode", "static") == "emotion" and getattr(config, "music_library", None):
        _mix_emotion_music(config, board, shot_audios, all_segments)
    elif config.music_path and Path(config.music_path).exists():
        # Static mode: mix_background_music đã có afade in/out — phủ cả intro/outro card.
        with_music = config.work_dir / "final_music.mp4"
        ffmpeg_ops.mix_background_music(
            config.final_path, Path(config.music_path), with_music, config.music_duck_db
        )
        with_music.replace(config.final_path)
        log.info("Đã trộn nhạc nền tĩnh vào final.")

    if config.target_minutes is not None:
        actual_s = ffmpeg_ops.probe_duration(config.final_path)
        target_s = config.target_minutes * 60
        if is_duration_off(actual_s, target_s):
            log.warning(
                "Thời lượng thực tế %.1fs lệch khỏi mục tiêu %.1fs (%.0f%%) — "
                "điều chỉnh số shot hoặc narration để bám --target-minutes %.1f.",
                actual_s,
                target_s,
                abs(actual_s / target_s - 1) * 100,
                config.target_minutes,
            )

    log.info("Storyboard hoàn tất. Final: %s", config.final_path)
    return config.final_path


def _mix_emotion_music(
    config: "PipelineConfig",
    board: "Storyboard",
    shot_audios: "list[Path]",
    all_segments: "list[Path]",
) -> None:
    """Trộn nhạc emotion vào final.mp4 theo mood mỗi shot.

    Quy trình:
    1. Tính thời lượng thực của từng shot audio.
    2. Dựng music timeline (gộp mood liền kề).
    3. Map mood → file nhạc trong music_library.
    4. mix_emotion_tracks → emotion_music.mp3 (chỉ nhạc, không giọng).
    5. mix_background_music (static duck) → trộn nhạc emotion vào final.

    Nếu thiếu file nhạc cho 1 mood → log warning, bỏ qua mood mode, giữ nguyên final.
    """
    from videopipe.music import build_music_timeline

    music_lib = Path(config.music_library)
    if not music_lib.is_dir():
        log.warning(
            "music_library '%s' không phải thư mục — bỏ qua emotion music.",
            music_lib,
        )
        return

    # Tính duration thực từng shot (đúng thứ tự, không tính card).
    shot_durs: list[float] = [ffmpeg_ops.probe_duration(a) for a in shot_audios]

    timeline = build_music_timeline(board.shots, shot_durs)

    # Map mood → file nhạc trong library (layout assets/music/<mood>/*.mp3).
    mood_files: dict[str, Path] = {}
    missing: list[str] = []
    for seg in timeline:
        mood = seg["mood"]
        if mood in mood_files:
            continue
        candidates = sorted((music_lib / mood).glob("*.mp3"))
        if candidates:
            mood_files[mood] = candidates[0]
        else:
            missing.append(mood)

    if missing:
        log.warning(
            "Thiếu file nhạc cho mood %s trong '%s' — bỏ qua emotion music.",
            missing, music_lib,
        )
        return

    emotion_audio = config.work_dir / "_emotion_music.mp3"
    ffmpeg_ops.mix_emotion_tracks(
        timeline=timeline,
        mood_files=mood_files,
        out_audio=emotion_audio,
    )

    with_music = config.work_dir / "final_music.mp4"
    ffmpeg_ops.mix_background_music(
        config.final_path, emotion_audio, with_music, config.music_duck_db
    )
    with_music.replace(config.final_path)
    log.info("Đã trộn nhạc emotion vào final (%d segment, %d mood).", len(timeline), len(mood_files))

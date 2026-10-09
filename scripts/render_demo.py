"""Render real screen recordings with an edited timeline and Chinese subtitles.

Timeline times are seconds in the original recording. This script only changes
framing, cuts, and subtitles; it never draws replacement application UI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from datetime import datetime, timezone

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FPS = 30
WIDTH, HEIGHT = 1920, 1080
VIDEO_NAME = "PaperVault-demo-zh.mp4"
SRT_NAME = "PaperVault-demo-zh.srt"
ASS_NAME = "PaperVault-demo-zh.ass"
DELIVERABLES = (VIDEO_NAME, SRT_NAME, ASS_NAME, "poster.jpg", "contact-sheet.jpg", "render.log", "render-report.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seconds(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number of seconds")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def inspect_video(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"OpenCV could not open video: {path}")
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if frame_count < 1 or fps <= 0 or not math.isfinite(fps):
            raise ValueError(f"Invalid video duration or frame rate: {path}")
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
        return {
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": fps, "frames": frame_count, "duration": frame_count / fps,
            "codec_tag": "".join(chr((fourcc >> (8 * index)) & 255) for index in range(4)),
        }
    finally:
        capture.release()


def load_font(size: int) -> ImageFont.FreeTypeFont:
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
    if not font.is_file():
        raise FileNotFoundError(f"Chinese subtitle font is missing: {font}")
    return ImageFont.truetype(str(font), size=size)


def wrap_subtitle(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Every cue needs nonempty text")
    if any(ord(character) < 32 and character not in "\n\r\t" for character in text):
        raise ValueError("Subtitle text contains control characters")
    font = load_font(36)
    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        current = ""
        for character in paragraph.replace("\t", " ").strip():
            if current and font.getlength(current + character) > 1740:
                lines.append(current.rstrip())
                current = ""
            current += character
        if current:
            lines.append(current.rstrip())
    if len(lines) > 2:
        raise ValueError(f"Subtitle would exceed two lines; shorten it: {text!r}")
    return "\n".join(lines)


def normalize_timeline(data: dict, duration: float) -> tuple[list[dict], list[dict]]:
    raw_clips = data.get("clips")
    raw_cues = data.get("cues", [])
    if not isinstance(raw_clips, list) or not 1 <= len(raw_clips) <= 64:
        raise ValueError("clips must contain between 1 and 64 clip objects")
    if not isinstance(raw_cues, list):
        raise ValueError("cues must be a list")
    clips: list[dict] = []
    cursor_frames = 0
    for index, clip in enumerate(raw_clips):
        start = seconds(clip["start"], f"clip {index + 1} start")
        end = seconds(clip["end"], f"clip {index + 1} end")
        if end <= start or end > duration + 0.05:
            raise ValueError(f"Clip {index + 1} lies outside the video or has no duration")
        frames = max(1, round((end - start) * FPS))
        clips.append({"start": start, "end": min(end, duration), "frames": frames,
                      "output_start": cursor_frames / FPS, "output_end": (cursor_frames + frames) / FPS})
        cursor_frames += frames
    cues: list[dict] = []
    prepared_cues: list[dict] = []
    for index, cue in enumerate(raw_cues):
        start = seconds(cue["start"], f"cue {index + 1} start")
        end = seconds(cue["end"], f"cue {index + 1} end")
        if end <= start or end > duration + 0.05:
            raise ValueError(f"Cue {index + 1} lies outside the video or has no duration")
        prepared_cues.append({"start": start, "end": end, "text": wrap_subtitle(cue["text"])})
    for clip_index, clip in enumerate(clips):
        for cue_index, cue in enumerate(prepared_cues):
            intersection_start = max(cue["start"], clip["start"])
            intersection_end = min(cue["end"], clip["end"])
            if intersection_end <= intersection_start:
                continue
            start = min(clip["output_end"], clip["output_start"] + intersection_start - clip["start"])
            end = min(clip["output_end"], clip["output_start"] + intersection_end - clip["start"])
            if end - start >= 0.01:
                cues.append({"start": start, "end": end, "text": cue["text"],
                             "source_cue": cue_index, "source_clip": clip_index})
    cues.sort(key=lambda cue: (cue["start"], cue["end"]))
    for previous, current in zip(cues, cues[1:]):
        if current["start"] < previous["end"] - 0.001:
            raise ValueError("Overlapping subtitles would obscure each other after editing")
    return clips, cues


def timestamp(value: float, ass: bool = False) -> str:
    denominator = 100 if ass else 1000
    units = round(value * denominator)
    whole, fraction = divmod(units, denominator)
    hours, remainder = divmod(whole, 3600)
    minutes, seconds_value = divmod(remainder, 60)
    if ass:
        return f"{hours}:{minutes:02d}:{seconds_value:02d}.{fraction:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds_value:02d},{fraction:03d}"


def write_subtitles(directory: Path, cues: list[dict], title: str) -> None:
    srt = "\n\n".join(f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
                      for index, cue in enumerate(cues, 1))
    (directory / SRT_NAME).write_text(srt + "\n", encoding="utf-8", newline="\n")
    ass = ["[Script Info]", f"Title: {title.replace(chr(10), ' ').replace(chr(13), ' ')}",
           "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2",
           "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Default,Microsoft YaHei,36,&H00FFFFFF,&H00FFFFFF,&H00171717,&H00171717,0,0,0,0,100,100,0,0,1,1,0,2,80,80,22,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for cue in cues:
        text = cue["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
        ass.append(f"Dialogue: 0,{timestamp(cue['start'], True)},{timestamp(cue['end'], True)},Default,,0,0,0,,{text}")
    (directory / ASS_NAME).write_text("\n".join(ass) + "\n", encoding="utf-8-sig", newline="\n")


def mp4_atoms(path: Path) -> list[str]:
    atoms: list[str] = []
    total = path.stat().st_size
    with path.open("rb") as stream:
        while stream.tell() < total:
            position = stream.tell()
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated MP4 atom")
            size, kind = struct.unpack(">I4s", header)
            if size == 1:
                size = struct.unpack(">Q", stream.read(8))[0]
            if size == 0:
                size = total - position
            if size < 8 or position + size > total:
                raise ValueError("Invalid MP4 atom size")
            atoms.append(kind.decode("ascii", errors="replace"))
            stream.seek(position + size)
    return atoms


def inspect_frames(path: Path, directory: Path, clips: list[dict], cues: list[dict]) -> dict:
    info = inspect_video(path)
    expected_frames = sum(clip["frames"] for clip in clips)
    if (info["width"], info["height"]) != (WIDTH, HEIGHT) or abs(info["fps"] - FPS) > 0.01:
        raise ValueError(f"Output dimensions or frame rate are wrong: {info}")
    if abs(info["frames"] - expected_frames) > 1:
        raise ValueError(f"Output duration mismatch: expected {expected_frames} frames, got {info['frames']}")
    atoms = mp4_atoms(path)
    if "moov" not in atoms or "mdat" not in atoms or atoms.index("moov") > atoms.index("mdat"):
        raise ValueError("Output MP4 is not configured for fast start")
    sample_indices = {0, info["frames"] - 1}
    # Include each edited section and subtitle onset, then retain up to 12
    # evenly spaced candidates so that the contact sheet stays readable.
    for clip in clips:
        sample_indices.add(min(info["frames"] - 1, round((clip["output_start"] + clip["output_end"]) * FPS / 2)))
    for cue in cues:
        sample_indices.add(min(info["frames"] - 1, round((cue["start"] + cue["end"]) * FPS / 2)))
    ordered = sorted(sample_indices)
    if len(ordered) > 12:
        ordered = [ordered[round(index * (len(ordered) - 1) / 11)] for index in range(12)]
    capture = cv2.VideoCapture(str(path))
    samples = []
    thumbnails = []
    poster_index = ordered[min(2, len(ordered) - 1)]
    try:
        for index in ordered:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            success, frame = capture.read()
            if not success or frame.shape[:2] != (HEIGHT, WIDTH):
                raise ValueError(f"Could not decode output frame {index}")
            if float(frame[:960].std()) < 1:
                raise ValueError(f"Application area appears blank at output frame {index}")
            # Caption padding is a separate dark region. Check its far corners
            # outside the 80-pixel subtitle margins, tolerating H.264 rounding.
            for region in (frame[980:1060, 10:50], frame[980:1060, 1870:1910]):
                if abs(float(region.mean()) - 23) > 5 or float(region.std()) > 5:
                    raise ValueError(f"Subtitle padding is not isolated at output frame {index}")
            picture = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if index == poster_index:
                picture.save(directory / "poster.jpg", quality=94)
            thumb = picture.resize((640, 360), Image.Resampling.LANCZOS)
            thumbnails.append((index / FPS, thumb))
            samples.append({"frame": index, "seconds": round(index / FPS, 3), "decoded": True,
                            "application_pixel_stddev": round(float(frame[:960].std()), 3)})
    finally:
        capture.release()
    sheet = Image.new("RGB", (1920, math.ceil(len(thumbnails) / 3) * 398), "#222222")
    draw = ImageDraw.Draw(sheet)
    font = load_font(22)
    for index, (time, thumb) in enumerate(thumbnails):
        x, y = (index % 3) * 640, (index // 3) * 398
        sheet.paste(thumb, (x, y))
        draw.text((x + 16, y + 368), timestamp(time), fill="white", font=font)
    sheet.save(directory / "contact-sheet.jpg", quality=92)
    return {**info, "expected_frames": expected_frames, "mp4_top_level_atoms": atoms,
            "fast_start": True, "samples": samples, "isolated_subtitle_padding": True}


def render(args: argparse.Namespace) -> dict:
    timeline = args.timeline.resolve(strict=True)
    data = json.loads(timeline.read_text(encoding="utf-8-sig"))
    raw = Path(data["raw_video"])
    output = Path(data["output_directory"])
    if not raw.is_absolute() or not output.is_absolute():
        raise ValueError("raw_video and output_directory must be absolute paths")
    raw = raw.resolve(strict=True)
    output = output.resolve()
    ffmpeg = args.ffmpeg.resolve(strict=True)
    for name in DELIVERABLES:
        destination = output / name
        if destination in (raw, timeline):
            raise ValueError("Output would overwrite the source video or timeline")
        if destination.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite {destination}; pass --overwrite explicitly")
    source_info = inspect_video(raw)
    clips, cues = normalize_timeline(data, source_info["duration"])
    title = str(data.get("title", "PaperVault 0.2.2 操作演示"))
    output.mkdir(parents=True, exist_ok=True)
    # TemporaryDirectory is inside the output directory: final os.replace
    # operations stay on the same volume, and incomplete encodes stay private.
    with tempfile.TemporaryDirectory(prefix=".render-", dir=output) as temporary:
        staging = Path(temporary)
        write_subtitles(staging, cues, title)
        command = [str(ffmpeg), "-hide_banner", "-nostdin", "-y", "-filter_complex_threads", "2"]
        filters = []
        for index, clip in enumerate(clips):
            command.extend(["-ss", f"{clip['start']:.6f}", "-t", f"{clip['end'] - clip['start']:.6f}",
                            "-threads", "2", "-i", str(raw)])
            filters.append(
                f"[{index}:v:0]setpts=PTS-STARTPTS,fps={FPS}:start_time=0,"
                f"tpad=stop_mode=clone:stop_duration=0.04,trim=end_frame={clip['frames']},"
                "scale=1920:960:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,"
                f"pad=1920:960:(ow-iw)/2:(oh-ih)/2:color=black,pad=1920:1080:0:0:color=0x171717[v{index}]"
            )
        inputs = "".join(f"[v{index}]" for index in range(len(clips)))
        filters.append(f"{inputs}concat=n={len(clips)}:v=1:a=0,ass=filename='{ASS_NAME}'[out]")
        command.extend(["-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-c:v", "libx264",
                        "-preset", args.preset, "-crf", "20", "-threads", "4", "-pix_fmt", "yuv420p",
                        "-r", str(FPS), "-fps_mode", "cfr", "-movflags", "+faststart",
                        "-metadata", f"title={title}", "-metadata", "comment=Real screen recording; edited with Chinese subtitles",
                        VIDEO_NAME])
        log = staging / "render.log"
        with log.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("ENCODE COMMAND\n" + json.dumps(command, ensure_ascii=False) + "\n")
            stream.flush()
            result = subprocess.run(command, cwd=staging, stdin=subprocess.DEVNULL, stdout=stream,
                                    stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"FFmpeg encoding failed ({result.returncode}):\n{log.read_text(encoding='utf-8', errors='replace')[-12000:]}")
        rendered = staging / VIDEO_NAME
        validation = inspect_frames(rendered, staging, clips, cues)
        decode_command = [str(ffmpeg), "-hide_banner", "-nostdin", "-i", str(rendered),
                          "-map", "0:v:0", "-an", "-f", "null", "-"]
        decoded = subprocess.run(decode_command, stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", check=False)
        with log.open("a", encoding="utf-8") as stream:
            stream.write("\nFULL DECODE\n" + decoded.stderr)
        if decoded.returncode or re.search(r"error while|invalid data|corrupt decoded|decoding error", decoded.stderr, re.I):
            raise RuntimeError(f"Full output decode failed:\n{decoded.stderr[-6000:]}")
        if re.search(r"Stream #\d+:\d+.*Audio:", decoded.stderr):
            raise ValueError("Unexpected audio track in silent demo")
        if not re.search(r"Video: h264.*yuv420p", decoded.stderr):
            raise ValueError("Output codec or pixel format is not H.264 / yuv420p")
        validation.update({"full_decode_passed": True, "audio_tracks": 0, "pixel_format": "yuv420p", "codec": "h264"})
        report = {
            "passed": True, "created_at_utc": datetime.now(timezone.utc).isoformat(), "title": title,
            "timeline": str(timeline), "timeline_sha256": sha256(timeline), "raw_video": str(raw),
            "raw_sha256": sha256(raw), "source": source_info, "output_directory": str(output),
            "ffmpeg": str(ffmpeg), "ffmpeg_sha256": sha256(ffmpeg), "clips": clips, "mapped_cues": cues,
            "validation": validation, "framing": {"ui_area": [0, 0, 1920, 960], "subtitle_area": [0, 960, 1920, 1080],
                                                   "font": "Microsoft YaHei", "font_size": 36, "max_lines": 2},
            "notes": ["Clip durations quantized to the nearest 30 fps frame; boundary frames may repeat by at most one frame.",
                      "Automated decoding and sampled pixels are verified; visual review of the contact sheet is still required."],
            "artifacts": {name: {"path": str(output / name), "bytes": (staging / name).stat().st_size,
                                 "sha256": sha256(staging / name)} for name in DELIVERABLES if name != "render-report.json"},
        }
        (staging / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        # Validate every file before publishing any of them; the report is last
        # so its existence can be used as the completed render marker.
        for name in DELIVERABLES:
            if not (staging / name).is_file():
                raise RuntimeError(f"Missing staged deliverable: {name}")
            if (output / name).exists() and not args.overwrite:
                raise FileExistsError(f"Output appeared during rendering: {output / name}")
        for name in DELIVERABLES:
            if args.overwrite:
                os.replace(staging / name, output / name)
            else:
                # On Windows os.rename rejects a destination created since the
                # last check, preserving the default no-overwrite guarantee.
                os.rename(staging / name, output / name)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, default=ROOT / ".tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe")
    parser.add_argument("--preset", choices=("ultrafast", "fast", "medium", "slow"), default="medium")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = render(args)
    print(json.dumps({"passed": report["passed"], "video": report["artifacts"][VIDEO_NAME]["path"],
                      "duration": report["validation"]["duration"], "report": str(Path(report["output_directory"]) / "render-report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

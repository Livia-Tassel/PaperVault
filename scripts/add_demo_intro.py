"""Add a silent, centered Chinese typewriter introduction to a recorded demo."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

import cv2
from PIL import Image, ImageDraw

from render_demo import ROOT, inspect_video, load_font, mp4_atoms, sha256, timestamp


WIDTH, HEIGHT, FPS = 1920, 1080, 30
FONT_SIZE = 68
SEGMENTS = [
    {"text": "读过的论文，能成为你的知识资产吗？", "frames": 108, "typing_frames": 54},
    {"text": "PaperVault，把论文变成可检索的本地知识库。", "frames": 108, "typing_frames": 60},
    {"text": "正文、图表，跨论文一起找。", "frames": 90, "typing_frames": 45},
    {"text": "找到线索，一键回到原文。", "frames": 81, "typing_frames": 42},
]
BLACK_FRAMES = 9
INTRO_FRAMES = sum(segment["frames"] for segment in SEGMENTS) + BLACK_FRAMES
INTRO_SECONDS = INTRO_FRAMES / FPS
MOVIE = "PaperVault-library-demo-zh.mp4"
SUBTITLES = "PaperVault-library-demo-zh.srt"


def timed_segments():
    cursor = 0
    for segment in SEGMENTS:
        yield {**segment, "start_frame": cursor, "end_frame": cursor + segment["frames"],
               "start_seconds": cursor / FPS, "end_seconds": (cursor + segment["frames"]) / FPS,
               "fully_visible_seconds": (cursor + segment["typing_frames"]) / FPS}
        cursor += segment["frames"]


def build_frame(segment, local_frame, font):
    picture = Image.new("RGB", (WIDTH, HEIGHT), "black")
    text = segment["text"]
    count = min(len(text), math.floor(local_frame * len(text) / segment["typing_frames"]))
    visible = text[:count]
    full_width = font.getlength(text)
    if full_width > WIDTH - 160:
        raise ValueError("Intro sentence does not fit the centered text region")
    bbox = font.getbbox(text)
    left = (WIDTH - full_width) / 2
    top = (HEIGHT - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw = ImageDraw.Draw(picture)
    if visible:
        draw.text((left, top), visible, font=font, fill=(238, 238, 238))
    cursor_on = local_frame < segment["typing_frames"] or ((local_frame - segment["typing_frames"]) // 12) % 2 == 0
    if cursor_on:
        x = round(left + font.getlength(visible) + 9)
        y = (HEIGHT - FONT_SIZE) // 2
        draw.rectangle((x, y, x + 1, y + FONT_SIZE - 1), fill=(205, 205, 205))
    return picture, count, cursor_on


def create_intro(ffmpeg, stage):
    font = load_font(FONT_SIZE)
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-n", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s:v", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "pipe:0", "-an",
               "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4", "-pix_fmt", "yuv420p",
               "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-movflags", "+faststart", "intro.mp4"]
    with (stage / "intro-encode.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=stage, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for segment in SEGMENTS:
                last_key, last_bytes = None, None
                for frame_index in range(segment["frames"]):
                    count = min(len(segment["text"]), math.floor(frame_index * len(segment["text"]) / segment["typing_frames"]))
                    cursor = frame_index < segment["typing_frames"] or ((frame_index - segment["typing_frames"]) // 12) % 2 == 0
                    key = (count, cursor)
                    if key != last_key:
                        picture, _, _ = build_frame(segment, frame_index, font)
                        last_bytes, last_key = picture.tobytes(), key
                    process.stdin.write(last_bytes)
            blank = Image.new("RGB", (WIDTH, HEIGHT), "black").tobytes()
            for _ in range(BLACK_FRAMES):
                process.stdin.write(blank)
            process.stdin.close()
            if process.wait(timeout=120):
                raise RuntimeError("Intro encoding failed; inspect intro-encode.log")
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            raise


def validate_video(ffmpeg, video, stage, log_name, expected_frames):
    info = inspect_video(video)
    if (info["width"], info["height"]) != (WIDTH, HEIGHT) or abs(info["fps"] - FPS) > 0.01:
        raise ValueError(f"Unexpected video format: {info}")
    if abs(info["frames"] - expected_frames) > 1:
        raise ValueError(f"Unexpected video length: {info['frames']} frames; expected {expected_frames}")
    result = subprocess.run([str(ffmpeg), "-hide_banner", "-nostdin", "-i", str(video), "-map", "0:v:0", "-an", "-f", "null", "-"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    (stage / log_name).write_text(result.stderr, encoding="utf-8")
    if result.returncode or re.search(r"error while|invalid data|corrupt decoded|decoding error", result.stderr, re.I):
        raise RuntimeError("Full video decode failed")
    if not re.search(r"Video: h264.*yuv420p", result.stderr) or re.search(r"Stream #\d+:\d+.*Audio:", result.stderr):
        raise ValueError("Expected a silent H.264 / yuv420p video")
    atoms = mp4_atoms(video)
    if atoms.index("moov") > atoms.index("mdat"):
        raise ValueError("MP4 is missing fast-start layout")
    return {**info, "full_decode_passed": True, "audio_tracks": 0, "fast_start": True, "sha256": sha256(video)}


def sample_intro(stage):
    samples = [0, 18, 54, 90, 108, 138, 168, 215, 246, 276, 348, INTRO_FRAMES - 1]
    capture = cv2.VideoCapture(str(stage / "intro.mp4"))
    sheet = Image.new("RGB", (1920, 4 * 392), "#171717")
    draw = ImageDraw.Draw(sheet)
    font = load_font(21)
    evidence = []
    try:
        for position, frame_index in enumerate(samples):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Intro frame {frame_index} could not be decoded")
            if frame_index == INTRO_FRAMES - 1 and frame.max() > 5:
                raise ValueError("The last intro frame must be entirely black")
            picture = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if frame_index == 90:
                picture.save(stage / "poster.jpg", quality=95)
            x, y = (position % 3) * 640, (position // 3) * 392
            sheet.paste(picture.resize((640, 360), Image.Resampling.LANCZOS), (x, y))
            draw.text((x + 14, y + 365), f"{frame_index / FPS:.2f}s", font=font, fill="white")
            evidence.append({"frame": frame_index, "seconds": frame_index / FPS, "decoded": True,
                             "nonblack_pixels": int((frame.max(axis=2) > 25).sum())})
    finally:
        capture.release()
    sheet.save(stage / "intro-contact-sheet.jpg", quality=94)
    return evidence


def parse_srt(file):
    text = file.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    if not text:
        raise ValueError("Main demo subtitles are empty")
    pattern = re.compile(r"(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit() or not (match := pattern.fullmatch(lines[1])):
            raise ValueError("Invalid source SRT block")
        numbers = list(map(int, match.groups()))
        start = numbers[0] * 3600 + numbers[1] * 60 + numbers[2] + numbers[3] / 1000
        end = numbers[4] * 3600 + numbers[5] * 60 + numbers[6] + numbers[7] / 1000
        if end <= start or (cues and start < cues[-1]["end"] - 0.001):
            raise ValueError("Source SRT has overlapping or invalid times")
        cues.append({"start": start, "end": end, "text": "\n".join(lines[2:])})
    return cues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--subtitles", type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--intro-only", action="store_true", help="Render and validate only the 13.2 second introduction")
    args = parser.parse_args()
    if not args.intro_only and (args.demo is None or args.subtitles is None):
        parser.error("--demo and --subtitles are required unless --intro-only is used")
    output = args.output_directory.resolve()
    names = ["intro.mp4", "poster.jpg", "intro-contact-sheet.jpg", "intro-encode.log", "intro-decode.log", "intro-report.json"]
    if not args.intro_only:
        names += [MOVIE, SUBTITLES, "join-encode.log", "join-decode.log"]
    if any((output / name).exists() for name in names):
        raise FileExistsError("Refusing to overwrite an existing video or intro deliverable; use a new output directory")
    source_info, main_cues = None, []
    if not args.intro_only:
        args.demo, args.subtitles = args.demo.resolve(strict=True), args.subtitles.resolve(strict=True)
        source_info = inspect_video(args.demo)
        if (source_info["width"], source_info["height"]) != (WIDTH, HEIGHT) or abs(source_info["fps"] - FPS) > .01:
            raise ValueError("Source demo must already be 1920x1080 / 30 fps")
        main_cues = parse_srt(args.subtitles)
        if main_cues[-1]["end"] > source_info["duration"] + .1:
            raise ValueError("Source subtitles extend beyond the demo")
    ffmpeg = ROOT / ".tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
    if not ffmpeg.is_file():
        raise FileNotFoundError(ffmpeg)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".intro-", dir=output) as temporary:
        stage = Path(temporary)
        create_intro(ffmpeg, stage)
        intro = validate_video(ffmpeg, stage / "intro.mp4", stage, "intro-decode.log", INTRO_FRAMES)
        evidence = sample_intro(stage)
        report = {"passed": True, "created_at_utc": datetime.now(timezone.utc).isoformat(), "intro": intro,
                  "sentences": list(timed_segments()), "font": "Microsoft YaHei", "font_size": FONT_SIZE,
                  "foreground_rgb": [238, 238, 238], "background_rgb": [0, 0, 0], "trailing_black_frames": BLACK_FRAMES,
                  "typing": "Each Unicode character appears individually at evenly spaced frame boundaries; no word-level reveal.",
                  "samples": evidence, "ffmpeg": str(ffmpeg), "ffmpeg_sha256": sha256(ffmpeg), "source": None}
        if not args.intro_only:
            with (stage / "join-encode.log").open("wb") as log:
                result = subprocess.run([str(ffmpeg), "-hide_banner", "-nostdin", "-n", "-i", str(stage / "intro.mp4"), "-i", str(args.demo),
                    "-filter_complex", "[0:v:0]setpts=PTS-STARTPTS[a];[1:v:0]setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[out]",
                    "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4", "-pix_fmt", "yuv420p",
                    "-r", "30", "-fps_mode", "cfr", "-movflags", "+faststart", str(stage / MOVIE)],
                    stdout=subprocess.DEVNULL, stderr=log, check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                raise RuntimeError("Intro + demo encoding failed")
            report["video"] = validate_video(ffmpeg, stage / MOVIE, stage, "join-decode.log", INTRO_FRAMES + source_info["frames"])
            cues = [{"start": segment["start_seconds"], "end": segment["end_seconds"], "text": segment["text"]} for segment in timed_segments()]
            cues += [{**cue, "start": cue["start"] + INTRO_SECONDS, "end": cue["end"] + INTRO_SECONDS} for cue in main_cues]
            (stage / SUBTITLES).write_text("\n\n".join(f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
                for index, cue in enumerate(cues, 1)) + "\n", encoding="utf-8", newline="\n")
            report["source"] = {"video": str(args.demo), "video_sha256": sha256(args.demo), "metadata": source_info,
                                "subtitles": str(args.subtitles), "subtitles_sha256": sha256(args.subtitles),
                                "main_subtitles_shift_seconds": INTRO_SECONDS, "main_cue_count": len(main_cues),
                                "joined_cue_count": len(cues), "subtitles_burned_again": False}
        report["artifacts"] = {name: {"path": str(output / name), "bytes": (stage / name).stat().st_size,
                                      "sha256": sha256(stage / name)} for name in names if name != "intro-report.json"}
        (stage / "intro-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        for name in names:
            if (output / name).exists():
                raise FileExistsError(f"Output appeared during encoding: {output / name}")
        for name in names:
            os.rename(stage / name, output / name)
    print(json.dumps({"passed": True, "intro_seconds": INTRO_SECONDS, "report": str(output / "intro-report.json"),
                      "video": str(output / ("intro.mp4" if args.intro_only else MOVIE))}, ensure_ascii=False))


if __name__ == "__main__":
    main()

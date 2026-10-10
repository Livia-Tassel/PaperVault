"""Render a full-frame 1080p recording with local frosted-glass Chinese captions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from add_demo_intro import validate_video
from render_demo import ROOT, inspect_video, load_font, normalize_timeline, sha256, timestamp


WIDTH, HEIGHT, FPS = 1920, 1080, 30
VIDEO, SRT, ASS = "PaperVault-demo-zh.mp4", "PaperVault-demo-zh.srt", "PaperVault-demo-zh.ass"
FONT_SIZE, BOTTOM_MARGIN = 36, 42
NAMES = [VIDEO, SRT, ASS, "poster.jpg", "contact-sheet.jpg", "caption-mask.png", "render.log", "decode.log", "render-report.json"]


def wrap(text):
    font = load_font(FONT_SIZE)
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for character in paragraph:
            if current and font.getlength(current + character) > 1028:
                lines.append(current.rstrip())
                current = ""
            current += character
        if current:
            lines.append(current.strip())
    if len(lines) > 2:
        raise ValueError(f"Caption exceeds two readable lines: {text!r}")
    return "\n".join(lines)


def make_captions(stage, cues, title):
    font = load_font(FONT_SIZE)
    for cue in cues:
        cue["text"] = wrap(cue["text"])
    longest = max((font.getlength(line) for cue in cues for line in cue["text"].split("\n")), default=240)
    width = min(1100, max(320, math.ceil((longest + 72) / 2) * 2))
    height = 112 if any("\n" in cue["text"] for cue in cues) else 80
    x, y = (WIDTH - width) // 2, HEIGHT - BOTTOM_MARGIN - height
    scale = 4
    mask = Image.new("L", (width * scale, height * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=18 * scale, fill=255)
    mask.resize((width, height), Image.Resampling.LANCZOS).save(stage / "caption-mask.png")
    (stage / SRT).write_text("\n\n".join(f"{index}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}"
        for index, cue in enumerate(cues, 1)) + "\n", encoding="utf-8", newline="\n")
    script = ["[Script Info]", f"Title: {title.replace(chr(10), ' ').replace(chr(13), ' ')}",
              "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "ScaledBorderAndShadow: yes",
              "", "[V4+ Styles]",
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
              "Style: Default,Microsoft YaHei,36,&H00FFFFFF,&H00FFFFFF,&H80202020,&HFF000000,0,0,0,0,100,100,0,0,1,0.4,0,5,0,0,0,1",
              "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for cue in cues:
        text = cue["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
        cue_y = 42 if cue.get("position") == "top" else y
        position = "{\\pos(" + f"960,{cue_y + height / 2:g}" + ")}"
        script.append(f"Dialogue: 0,{timestamp(cue['start'], True)},{timestamp(cue['end'], True)},Default,,0,0,0,,{position}{text}")
    (stage / ASS).write_text("\n".join(script) + "\n", encoding="utf-8-sig", newline="\n")
    return {"x": x, "y": y, "width": width, "height": height, "bottom_margin": BOTTOM_MARGIN,
            "corner_radius": 18, "black_tint_opacity": .44, "blur_radius": 12, "blur_passes": 2,
            "font": "Microsoft YaHei", "font_size": FONT_SIZE, "maximum_lines": 2,
            "positions": {"bottom": y, "top": 42}}


def source_time(clips, output_seconds):
    clip = next((clip for clip in clips if clip["output_start"] <= output_seconds < clip["output_end"]), clips[-1])
    return min(clip["end"] - 1 / FPS, clip["start"] + output_seconds - clip["output_start"])


def inspect_samples(video, source, stage, clips, cues, panel):
    info = inspect_video(video)
    indices = {0, info["frames"] - 1}
    indices.update(min(info["frames"] - 1, round((cue["start"] + cue["end"]) * FPS / 2)) for cue in cues)
    indices = sorted(indices)
    if len(indices) > 12:
        indices = [indices[round(index * (len(indices) - 1) / 11)] for index in range(12)]
    capture, original = cv2.VideoCapture(str(video)), cv2.VideoCapture(str(source))
    sheet = Image.new("RGB", (1920, math.ceil(len(indices) / 3) * 394), "#222222")
    draw, font = ImageDraw.Draw(sheet), load_font(21)
    samples = []
    x, y, width, height = (panel[key] for key in ("x", "y", "width", "height"))
    outside = np.ones((HEIGHT, WIDTH), dtype=bool)
    for panel_y in panel["positions"].values():
        outside[panel_y - 3:panel_y + height + 3, x - 3:x + width + 3] = False
    try:
        for position, index in enumerate(indices):
            seconds = index / FPS
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok or frame.shape[:2] != (HEIGHT, WIDTH):
                raise RuntimeError(f"Output frame {index} did not decode")
            when = source_time(clips, seconds)
            original.set(cv2.CAP_PROP_POS_MSEC, when * 1000)
            ok, source_frame = original.read()
            if not ok:
                raise RuntimeError(f"Source frame at {when:.3f}s did not decode")
            cue = next((cue for cue in cues if cue["start"] <= seconds < cue["end"]), None)
            current_y = panel["positions"][cue.get("position", "bottom")] if cue else y
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if position == min(2, len(indices) - 1):
                image.save(stage / "poster.jpg", quality=95)
            left, top = (position % 3) * 640, (position // 3) * 394
            sheet.paste(image.resize((640, 360), Image.Resampling.LANCZOS), (left, top))
            draw.text((left + 14, top + 366), timestamp(seconds), font=font, fill="white")
            # Measure real pixels separately from caption text. The upper strip
            # of the panel is padding, so it reveals underlying blur/darkening.
            background = frame[current_y + 5:current_y + 13, x + 30:x + width - 30]
            before = source_frame[current_y + 5:current_y + 13, x + 30:x + width - 30]
            samples.append({"frame": index, "seconds": seconds, "source_seconds": round(when, 6),
                            "caption": cue["text"] if cue else None, "caption_position": cue.get("position", "bottom") if cue else None, "decoded": True,
                            "outside_panel_mean_abs_error": round(float(np.abs(frame.astype(np.float32) - source_frame.astype(np.float32))[outside].mean()), 3),
                            "panel_padding_mean_rgb": [round(float(value), 3) for value in background.mean(axis=(0, 1))[::-1]],
                            "panel_padding_laplacian_variance": round(float(cv2.Laplacian(cv2.cvtColor(background, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()), 3),
                            "source_padding_laplacian_variance": round(float(cv2.Laplacian(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()), 3)})
    finally:
        capture.release()
        original.release()
    sheet.save(stage / "contact-sheet.jpg", quality=94)
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", required=True, type=Path)
    parser.add_argument("--preset", choices=("fast", "medium", "slow"), default="fast")
    args = parser.parse_args()
    timeline = args.timeline.resolve(strict=True)
    data = json.loads(timeline.read_text(encoding="utf-8-sig"))
    source, output = Path(data["raw_video"]), Path(data["output_directory"])
    if not source.is_absolute() or not output.is_absolute():
        raise ValueError("raw_video and output_directory must be absolute")
    source, output = source.resolve(strict=True), output.resolve()
    source_info = inspect_video(source)
    if (source_info["width"], source_info["height"]) != (WIDTH, HEIGHT):
        raise ValueError("v2 requires an actual 1920x1080 capture; letterboxing or stretching 1920x960 footage is not allowed")
    for name in NAMES:
        if (output / name).exists() or output / name in (source, timeline):
            raise FileExistsError(f"Refusing to overwrite {output / name}; select a new output directory")
    clips, cues = normalize_timeline(data, source_info["duration"])
    for cue in cues:
        position = data["cues"][cue["source_cue"]].get("position", "bottom")
        if position not in ("bottom", "top"):
            raise ValueError("Cue position must be 'bottom' or 'top'")
        cue["position"] = position
    title = str(data.get("title", "PaperVault 操作演示"))
    ffmpeg = ROOT / ".tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".render-v2-", dir=output) as temporary:
        stage = Path(temporary)
        panel = make_captions(stage, cues, title)
        command = [str(ffmpeg), "-hide_banner", "-nostdin", "-n", "-filter_complex_threads", "2"]
        filters = []
        for index, clip in enumerate(clips):
            command += ["-ss", f"{clip['start']:.6f}", "-t", f"{clip['end'] - clip['start']:.6f}", "-threads", "2", "-i", str(source)]
            filters.append(f"[{index}:v:0]setpts=PTS-STARTPTS,fps=30:start_time=0,tpad=stop_mode=clone:stop_duration=0.04,trim=end_frame={clip['frames']},setsar=1[v{index}]")
        command += ["-loop", "1", "-framerate", "30", "-i", "caption-mask.png"]
        inputs = "".join(f"[v{index}]" for index in range(len(clips)))
        positions = sorted({cue["position"] for cue in cues}) or ["bottom"]
        filters += [f"{inputs}concat=n={len(clips)}:v=1:a=0,split={len(positions) + 1}[base]" + "".join(f"[backdrop{index}]" for index in range(len(positions))),
                    f"[{len(clips)}:v:0]format=gray,split={len(positions)}" + "".join(f"[mask{index}]" for index in range(len(positions)))]
        previous = "base"
        for index, position in enumerate(positions):
            panel_y = panel["positions"][position]
            active = "+".join(f"gte(t,{cue['start']:.6f})*lt(t,{cue['end']:.6f})" for cue in cues if cue["position"] == position) or "0"
            filters += [f"[backdrop{index}]crop={panel['width']}:{panel['height']}:{panel['x']}:{panel_y},boxblur=12:2,format=rgba,colorchannelmixer=rr=0.56:gg=0.56:bb=0.56[blurred{index}]",
                        f"[blurred{index}][mask{index}]alphamerge=shortest=1[rounded{index}]",
                        f"[{previous}][rounded{index}]overlay=x={panel['x']}:y={panel_y}:enable='{active}':shortest=1:eof_action=pass[captioned{index}]"]
            previous = f"captioned{index}"
        filters.append(f"[{previous}]ass=filename='{ASS}'[out]")
        command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-c:v", "libx264", "-preset", args.preset,
                    "-crf", "18", "-threads", "4", "-pix_fmt", "yuv420p", "-r", "30", "-fps_mode", "cfr",
                    "-t", f"{clips[-1]['output_end']:.6f}", "-movflags", "+faststart", "-metadata", f"title={title}", VIDEO]
        with (stage / "render.log").open("w", encoding="utf-8") as log:
            log.write(json.dumps(command, ensure_ascii=False) + "\n")
            log.flush()
            result = subprocess.run(command, cwd=stage, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError((stage / "render.log").read_text(encoding="utf-8", errors="replace")[-12000:])
        validation = validate_video(ffmpeg, stage / VIDEO, stage, "decode.log", sum(clip["frames"] for clip in clips))
        samples = inspect_samples(stage / VIDEO, source, stage, clips, cues, panel)
        report = {"passed": True, "created_at_utc": datetime.now(timezone.utc).isoformat(), "timeline": str(timeline),
                  "timeline_sha256": sha256(timeline), "raw_video": str(source), "raw_sha256": sha256(source),
                  "source": source_info, "output_directory": str(output), "validation": validation, "clips": clips,
                  "mapped_cues": cues, "caption_panel": panel, "samples": samples, "ffmpeg": str(ffmpeg), "ffmpeg_sha256": sha256(ffmpeg),
                  "framing": {"application_bounds": [0, 0, WIDTH, HEIGHT], "letterboxing": False, "scaling": False,
                              "caption_backdrop": "The current source frame is cropped, genuinely box-blurred, dark-tinted at 44%, and composited through an antialiased rounded mask only during cues."},
                  "artifacts": {name: {"path": str(output / name), "bytes": (stage / name).stat().st_size,
                                       "sha256": sha256(stage / name)} for name in NAMES if name != "render-report.json"}}
        (stage / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        for name in NAMES:
            if (output / name).exists():
                raise FileExistsError(f"Output appeared during rendering: {output / name}")
        for name in NAMES:
            os.rename(stage / name, output / name)
    print(json.dumps({"passed": True, "duration": validation["duration"], "video": str(output / VIDEO),
                      "report": str(output / "render-report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

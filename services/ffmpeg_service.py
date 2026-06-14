"""
services/ffmpeg_service.py
Handles ALL FFmpeg operations. Optimized for low-CPU environments.
"""
import asyncio
import os
import re
import json
from typing import Callable, Awaitable, Optional

from utils.logger import ffmpeg_logger as log
from utils.helpers import run_subprocess, make_temp_path, safe_delete
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)


async def get_video_info(path: str) -> dict:
    code, out, err = await run_subprocess(
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", path,
    )
    if code != 0:
        raise RuntimeError(f"ffprobe failed: {err}")
    data = json.loads(out)
    info = {"width": 1280, "height": 720, "duration": 0.0, "fps": 25.0}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = stream.get("width", 1280)
            info["height"] = stream.get("height", 720)
            info["duration"] = float(data.get("format", {}).get("duration", 0))
            fps_str = stream.get("r_frame_rate", "25/1")
            try:
                num, den = fps_str.split("/")
                info["fps"] = round(float(num) / float(den), 3)
            except Exception:
                info["fps"] = 25.0
            break
    return info


def _scale_filter(width: int) -> str:
    """Auto-downscale to max 720p width for speed on low-CPU. Keeps aspect ratio."""
    if width > 1280:
        return "scale=1280:-2,"
    elif width > 854:
        return "scale=854:-2,"
    return ""


def _build_moving_text_filter(
    text: str, opacity: float, size_frac: float, speed: float,
    font_size: int, color: str, mode: str, video_w: int, video_h: int,
    add_scale: bool = True,
) -> str:
    # Scale font relative to (possibly downscaled) output width
    out_w = min(video_w, 1280) if add_scale and video_w > 1280 else video_w
    font_size_px = max(10, int(font_size * (out_w / 1280)))
    alpha = min(1.0, max(0.0, opacity))

    escaped = (
        text.replace("\\", "\\\\")
            .replace("'", "\u2019")
            .replace(":", "\\:")
            .replace("%", "\\%")
    )

    if mode == "static":
        x_expr = "(W-tw)/2"
        y_expr = "(H-th)/2"
    else:
        x_expr = f"abs(mod(t*{speed:.2f}, 2*(W-tw)) - (W-tw))"
        y_expr = f"abs(mod(t*{speed*0.7:.2f}+{video_h/3:.1f}, 2*(H-th)) - (H-th))"

    scale_part = _scale_filter(video_w) if add_scale else ""

    return (
        f"{scale_part}"
        f"drawtext=text='{escaped}'"
        f":fontsize={font_size_px}"
        f":fontcolor={color}@{alpha:.2f}"
        f":x='{x_expr}':y='{y_expr}'"
        f":borderw=2:bordercolor=black@{alpha*0.5:.2f}"
    )


def _build_moving_image_filter(
    overlay_path: str, opacity: float, size_frac: float,
    speed: float, mode: str, video_w: int, video_h: int,
) -> tuple:
    out_w = min(video_w, 1280) if video_w > 1280 else video_w
    wm_w = max(40, int(out_w * size_frac))
    alpha = min(1.0, max(0.0, opacity))
    scale_part = _scale_filter(video_w)

    if mode == "static":
        x_expr = "(W-overlay_w)/2"
        y_expr = "(H-overlay_h)/2"
    else:
        x_expr = f"abs(mod(t*{speed:.2f}, 2*(W-overlay_w)) - (W-overlay_w))"
        y_expr = f"abs(mod(t*{speed*0.7:.2f}+100, 2*(H-overlay_h)) - (H-overlay_h))"

    filter_complex = (
        f"[0:v]{scale_part}setsar=1[scaled];"
        f"[1:v]scale={wm_w}:-1,format=rgba,colorchannelmixer=aa={alpha:.2f}[wm];"
        f"[scaled][wm]overlay=x='{x_expr}':y='{y_expr}':eval=frame[out]"
    )
    return filter_complex, ["-i", overlay_path]


# ── Common encode flags (optimized for low-CPU free tier) ─────────────────
_ENCODE_FLAGS = [
    "-c:v", "libx264",
    "-preset", "ultrafast",   # fastest encoding
    "-tune", "zerolatency",   # removes look-ahead buffering overhead
    "-crf", "28",             # slightly lower quality = smaller file = faster
    "-threads", "2",          # 2 threads optimal for 0.1-0.5 CPU
    "-c:a", "copy",
    "-movflags", "+faststart",
]


async def apply_watermark_video(
    input_path: str,
    output_path: str,
    settings: dict,
    progress_cb: Optional[Callable[[float], Awaitable[None]]] = None,
) -> str:
    info = await get_video_info(input_path)
    w, h, duration = info["width"], info["height"], info["duration"]

    mode     = settings.get("mode", "moving")
    wm_image = settings.get("watermark_file_id")
    wm_text  = settings.get("watermark_text", "@Channel")
    opacity  = float(settings.get("opacity", 0.7))
    size     = float(settings.get("size", 0.2))
    speed    = float(settings.get("speed", 80.0))
    font_sz  = int(settings.get("font_size", 40))
    color    = settings.get("color", "white")

    cmd = ["ffmpeg", "-y", "-i", input_path]
    use_image_wm = wm_image and os.path.exists(str(wm_image))

    if use_image_wm:
        fc, extra = _build_moving_image_filter(wm_image, opacity, size, speed, mode, w, h)
        cmd += extra
        cmd += ["-filter_complex", fc, "-map", "[out]", "-map", "0:a?"] + _ENCODE_FLAGS + [output_path]
    else:
        vf = _build_moving_text_filter(wm_text, opacity, size, speed, font_sz, color, mode, w, h)
        cmd += ["-vf", vf] + _ENCODE_FLAGS + [output_path]

    log.info(f"FFmpeg cmd: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=10 * 1024 * 1024,  # 10MB buffer
    )

    ffmpeg_stderr_lines = []
    last_progress = 0.0
    _buf = b""

    async def read_stderr():
        nonlocal last_progress, _buf
        while True:
            try:
                chunk = await proc.stderr.read(65536)
            except Exception:
                break
            if not chunk:
                break
            _buf += chunk
            while b"\n" in _buf:
                line_b, _buf = _buf.split(b"\n", 1)
                decoded = line_b.decode(errors="replace").strip()
                if decoded:
                    ffmpeg_stderr_lines.append(decoded[-500:])
                if duration and duration > 0:
                    m = re.search(r"time=(\d+):(\d+):([\d.]+)", decoded)
                    if m:
                        elapsed = (int(m.group(1)) * 3600
                                   + int(m.group(2)) * 60
                                   + float(m.group(3)))
                        pct = min(99.0, (elapsed / duration) * 100)
                        if pct - last_progress >= 10.0:
                            last_progress = pct
                            if progress_cb:
                                try:
                                    await progress_cb(pct)
                                except Exception:
                                    pass

    await asyncio.gather(read_stderr(), proc.wait())
    rc = proc.returncode

    ffmpeg_log_path = os.path.join(LOGS_DIR, "ffmpeg.log")
    with open(ffmpeg_log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\nCMD: {' '.join(cmd)}\n")
        f.write("\n".join(ffmpeg_stderr_lines[-50:]))

    if rc != 0:
        raise RuntimeError(f"FFmpeg exited {rc}:\n" + "\n".join(ffmpeg_stderr_lines[-20:]))

    if progress_cb:
        try:
            await progress_cb(100.0)
        except Exception:
            pass

    return output_path


async def apply_watermark_image(
    input_path: str,
    output_path: str,
    settings: dict,
) -> str:
    wm_image = settings.get("watermark_file_id")
    wm_text  = settings.get("watermark_text", "@Channel")
    opacity  = float(settings.get("opacity", 0.7))
    size     = float(settings.get("size", 0.2))
    speed    = float(settings.get("speed", 80.0))
    font_sz  = int(settings.get("font_size", 40))
    color    = settings.get("color", "white")

    code, out, _ = await run_subprocess(
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", input_path,
    )
    w, h = 1280, 720
    try:
        data = json.loads(out)
        for s in data.get("streams", []):
            w = s.get("width", 1280); h = s.get("height", 720); break
    except Exception:
        pass

    use_image_wm = wm_image and os.path.exists(str(wm_image))
    if use_image_wm:
        wm_w = max(40, int(w * size))
        alpha = min(1.0, max(0.0, opacity))
        fc = (
            f"[1:v]scale={wm_w}:-1,format=rgba,colorchannelmixer=aa={alpha:.2f}[wm];"
            f"[0:v][wm]overlay=(W-overlay_w)/2:(H-overlay_h)/2[out]"
        )
        cmd = ["ffmpeg", "-y", "-i", input_path, "-i", wm_image,
               "-filter_complex", fc, "-map", "[out]", "-frames:v", "1", output_path]
    else:
        vf = _build_moving_text_filter(wm_text, opacity, size, speed, font_sz, color, "static", w, h)
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf, "-frames:v", "1", output_path]

    rc, _, stderr = await run_subprocess(*cmd)
    if rc != 0:
        raise RuntimeError(f"FFmpeg image failed:\n{stderr[-2000:]}")
    return output_path
    

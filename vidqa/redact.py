"""Black out regions of a recording so it can be shared (PII, tokens).

Solid fill, not blur — blurs and pixelation can be partially inverted;
an opaque box cannot. One ffmpeg pass, audio copied through. For an
excerpt, cut with `vidqa clip` first and redact the excerpt.
"""
import os

from .ffutil import ToolError, run
from .probe import probe


def redact(path, out, regions):
    if not regions:
        raise ToolError("give at least one --region x,y,w,h")
    info = probe(path)
    if info["video"] is None:
        raise ToolError("no video stream to redact")
    vw, vh = info["video"]["width"], info["video"]["height"]
    boxes = []
    for x, y, w, h in regions:
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > vw or y + h > vh:
            raise ToolError(f"region {x},{y},{w},{h} is outside the {vw}x{vh} frame")
        boxes.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", path, "-vf", ",".join(boxes),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", out])
    if not os.path.exists(out):
        raise ToolError(f"ffmpeg produced no output at {out}")
    return {"out": out, "regions": [list(r) for r in regions]}

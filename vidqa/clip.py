"""Cut a small excerpt (mp4 or gif) for bug tickets."""
import os

from .ffutil import ToolError, r4, run

GIF_FPS = 12
GIF_WIDTH = 480


def clip(path, out, start, end):
    if start < 0 or end <= start:
        raise ToolError("--from/--to want 0 <= from < to")
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start), "-t", str(end - start), "-i", path]
    ext = os.path.splitext(out)[1].lower()
    if ext == ".gif":
        args += ["-vf", f"fps={GIF_FPS},scale={GIF_WIDTH}:-2"]
    else:
        args += ["-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart"]
    run(args + [out])
    from .probe import probe
    return {
        "duration_s": probe(out)["duration_s"],
        "format": ext.lstrip("."),
        "from_s": r4(start),
        "out": out,
        "to_s": r4(end),
    }

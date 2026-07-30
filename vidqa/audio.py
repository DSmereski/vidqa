"""Audio glitch checks via ffmpeg's own filters: silences and clipping."""
import re

from .ffutil import ToolError, r4, run, safe_path

SILENCE_DB = -50       # silencedetect noise floor
SILENCE_MIN_S = 0.5    # minimum silence duration reported
CLIP_DB = -0.1         # max_volume at/above this reads as clipped
EVENT_CAP = 20


def audio(path):
    try:
        stderr = run([
            "ffmpeg", "-hide_banner", "-i", safe_path(path),
            "-af", f"silencedetect=n={SILENCE_DB}dB:d={SILENCE_MIN_S},volumedetect",
            "-vn", "-f", "null", "-",
        ]).stderr
    except ToolError as exc:
        if "does not contain any stream" in str(exc):
            raise ToolError(f"no audio stream in {path}")
        raise
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: (-?[\d.]+)", stderr)]
    durs = [float(m.group(1)) for m in re.finditer(r"silence_duration: ([\d.]+)", stderr)]
    silences = []
    for i, start in enumerate(starts):
        # audio that ends silent logs a start with no duration
        dur = durs[i] if i < len(durs) else None
        silences.append({
            "start_s": r4(max(0.0, start)),
            "duration_s": r4(dur) if dur is not None else None,
        })
    max_vol = _db(stderr, "max_volume")
    mean_vol = _db(stderr, "mean_volume")
    return {
        "silence_count": len(silences),
        "silences": silences[:EVENT_CAP],
        "max_volume_db": max_vol,
        "mean_volume_db": mean_vol,
        "clipping_suspected": bool(max_vol is not None and max_vol >= CLIP_DB),
    }


def _db(stderr, name):
    m = re.search(rf"{name}: (-?[\d.]+) dB", stderr)
    return r4(m.group(1)) if m else None

"""Frame-timing analysis of a recorded video.

Three independent signals, because capture mode changes where stutter shows up:
- pts deltas: gaps in timestamps (VFR captures);
- duplicate frames: encoded stutter in CFR captures (frame present, unchanged);
- freezes: runs of identical frames long enough to read as a hang.
"""
import re

from .ffutil import ToolError, r4, run, safe_path

STUTTER_FACTOR = 1.5   # a pts delta this many times the median counts as stutter
FREEZE_MIN_S = 0.4     # freezedetect minimum duration
EVENT_CAP = 20         # cap listed events; counts stay exact


def timing(path):
    pts, na_frames = _frame_pts(path)
    if len(pts) < 2:
        raise ToolError(f"fewer than 2 timestamped video frames in {path}")
    deltas = [(b - a) * 1000.0 for a, b in zip(pts, pts[1:])]
    ordered = sorted(deltas)
    median = ordered[len(ordered) // 2]
    threshold = median * STUTTER_FACTOR
    events = [
        {"t_s": r4(pts[i]), "delta_ms": r4(d)}
        for i, d in enumerate(deltas)
        if median > 0 and d > threshold
    ]
    freezes = _freezes(path)
    dup = _dup_frames(path, len(pts) + na_frames)
    return {
        "frame_count": len(pts),
        "na_frames": na_frames,
        "fps_effective": r4(1000.0 / median) if median > 0 else None,
        "frame_time_ms": {
            "p50": r4(_pct(ordered, 50)),
            "p95": r4(_pct(ordered, 95)),
            "p99": r4(_pct(ordered, 99)),
            "max": r4(ordered[-1]),
        },
        "stutter": {"event_count": len(events), "events": events[:EVENT_CAP]},
        "dup_frames": dup,
        "dup_ratio": r4(dup / (len(pts) + na_frames)),
        "freeze_count": len(freezes),
        "freezes": freezes[:EVENT_CAP],
    }


def _pct(ordered, p):
    """Nearest-rank percentile on a pre-sorted list."""
    rank = max(1, -(-len(ordered) * p // 100))
    return ordered[min(len(ordered), rank) - 1]


def _frame_pts(path):
    proc = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time",
        "-of", "csv=p=0", safe_path(path),
    ])
    pts = []
    na_frames = 0
    for line in proc.stdout.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            pts.append(float(line))
        except ValueError:
            na_frames += 1
    return pts, na_frames


def _dup_frames(path, total):
    stderr = run([
        "ffmpeg", "-hide_banner", "-i", safe_path(path),
        "-vf", "mpdecimate", "-an", "-f", "null", "-",
    ]).stderr
    kept = None
    for m in re.finditer(r"frame=\s*(\d+)", stderr):
        kept = int(m.group(1))
    if kept is None:
        raise ToolError("could not parse ffmpeg frame count from mpdecimate pass")
    return max(0, total - kept)


def _freezes(path):
    stderr = run([
        "ffmpeg", "-hide_banner", "-i", safe_path(path),
        "-vf", f"freezedetect=n=-60dB:d={FREEZE_MIN_S}", "-an", "-f", "null", "-",
    ]).stderr
    starts = [float(m.group(1)) for m in re.finditer(r"freeze_start: ([\d.]+)", stderr)]
    durs = [float(m.group(1)) for m in re.finditer(r"freeze_duration: ([\d.]+)", stderr)]
    freezes = []
    for i, start in enumerate(starts):
        # a video that ends still frozen logs a start with no duration
        dur = durs[i] if i < len(durs) else None
        freezes.append({
            "start_s": r4(start),
            "duration_s": r4(dur) if dur is not None else None,
        })
    return freezes

"""Shared ffmpeg/ffprobe helpers.

All vidqa output must be deterministic: floats rounded to 4 places, JSON keys
sorted, no wall-clock values anywhere.
"""
import json
import os
import shutil
import subprocess


class ToolError(RuntimeError):
    pass


def safe_path(path):
    """ffmpeg/ffprobe read a leading '-' as an option; anchor such paths."""
    path = str(path)
    return f".{os.sep}{path}" if path.startswith("-") else path


def run(args, timeout=None):
    """Run an external tool, raising ToolError with the tail of stderr on failure.

    The full stderr rides on the exception as `.stderr` so callers can match
    phrases without depending on the display truncation.
    """
    if shutil.which(args[0]) is None and not os.path.isfile(args[0]):
        raise ToolError(f"{args[0]} not found on PATH (install ffmpeg full build)")
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"{args[0]} timed out after {timeout}s")
    if proc.returncode != 0:
        exc = ToolError(f"{args[0]} failed ({proc.returncode}): {proc.stderr.strip()[-400:]}")
        exc.stderr = proc.stderr
        raise exc
    return proc


def require_file(path):
    if not os.path.exists(path):
        raise ToolError(f"file not found: {path}")
    return path


def ffprobe_json(path, *args):
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", *args, safe_path(path)])
    return json.loads(proc.stdout)


def sample_fps(step):
    """fps filter clause whose output frame i is what was ON SCREEN at i*step.

    The filter's default rounding (near) emits the frame from roughly
    (i + 0.5) * step, so every i*step label would run ~half a step early.
    round=up keeps sample i = the last frame with pts <= i*step — the frame
    a viewer saw at that instant (measured with a frame-indexed probe video).
    """
    return f"fps={1.0 / step}:round=up"


def r4(x):
    return round(float(x), 4)


def pct(ordered, p):
    """Nearest-rank percentile on a pre-sorted list."""
    rank = max(1, -(-len(ordered) * p // 100))
    return ordered[min(len(ordered), rank) - 1]


def jdump(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

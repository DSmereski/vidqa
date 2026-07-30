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


def run(args):
    """Run an external tool, raising ToolError with the tail of stderr on failure."""
    if shutil.which(args[0]) is None:
        raise ToolError(f"{args[0]} not found on PATH (install ffmpeg full build)")
    proc = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode != 0:
        raise ToolError(f"{args[0]} failed ({proc.returncode}): {proc.stderr.strip()[-400:]}")
    return proc


def ffprobe_json(path, *args):
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", *args, safe_path(path)])
    return json.loads(proc.stdout)


def r4(x):
    return round(float(x), 4)


def jdump(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

"""Live frame-time capture on Windows via Intel PresentMon (ETW ground truth)."""
import csv
import io
import os
import tempfile

from .ffutil import ToolError, pct, r4, run

PRESENTMON_ENV = "VIDQA_PRESENTMON"
ERR_NO_PRESENTMON = "PresentMon exe not found"  # stable contract prefix
# column name candidates across PresentMon 1.x / 2.x CSV schemas
DELTA_COLUMNS = ("msbetweenpresents", "frametime", "msbetweendisplaychange")


def live(process, seconds=10, presentmon=None):
    exe = presentmon or os.environ.get(PRESENTMON_ENV) or _bundled()
    if not exe or not os.path.exists(exe):
        raise ToolError(
            f"{ERR_NO_PRESENTMON}: pass --presentmon, set VIDQA_PRESENTMON, "
            "or drop PresentMon*.exe into the package's tools/ dir"
        )
    out = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    out.close()
    try:
        try:
            run([
                exe, "--process_name", process, "--output_file", out.name,
                "--timed", str(seconds), "--terminate_after_timed",
                "--stop_existing_session",
            ], timeout=seconds + 30)
        except ToolError as exc:
            if "access denied" in getattr(exc, "stderr", str(exc)).lower():
                raise ToolError(
                    "PresentMon needs ETW access (one-time setup): run from an "
                    "admin terminal, or in an elevated prompt run "
                    "'net localgroup \"Performance Log Users\" \"<your user>\" /add' "
                    "then sign out and back in"
                )
            raise
        with open(out.name, newline="", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    finally:
        os.unlink(out.name)
    return parse_csv(text, process=process, seconds=seconds)


def parse_csv(text, process=None, seconds=None):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ToolError("empty PresentMon capture (is the process presenting frames?)")
    by_lower = {name.strip().lower(): name for name in reader.fieldnames}
    column = next((by_lower[c] for c in DELTA_COLUMNS if c in by_lower), None)
    if column is None:
        raise ToolError(f"no frame-time column in capture: {reader.fieldnames}")
    deltas = []
    skipped_rows = 0
    for row in reader:
        try:
            deltas.append(float(row[column]))
        except (KeyError, TypeError, ValueError):
            skipped_rows += 1
    if len(deltas) < 2:
        raise ToolError("PresentMon captured fewer than 2 frames")
    ordered = sorted(deltas)
    mean = sum(deltas) / len(deltas)
    return {
        "process": process,
        "capture_seconds": seconds,
        "frame_count": len(deltas),
        "skipped_rows": skipped_rows,
        "fps_avg": r4(1000.0 / mean) if mean > 0 else None,
        "frame_time_ms": {
            "p50": r4(pct(ordered, 50)),
            "p95": r4(pct(ordered, 95)),
            "p99": r4(pct(ordered, 99)),
            "max": r4(ordered[-1]),
        },
    }


def _bundled():
    tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
    if not os.path.isdir(tools):
        return None
    for name in sorted(os.listdir(tools)):
        if name.lower().startswith("presentmon") and name.lower().endswith(".exe"):
            return os.path.join(tools, name)
    return None

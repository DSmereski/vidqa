"""Playwright trace.zip -> step timeline, and frames at named steps.

Stdlib zip+NDJSON parsing only — no Playwright dependency. Timestamps are
relative to the trace's first monotonic clock value, which coincides with
context creation; alignment to the context video is approximate (~100ms).
"""
import json
import zipfile

from .ffutil import ToolError, r4

STEP_CAP = 100


def trace(path, video=None, at_step=None, out=None):
    steps = _parse(path)
    result = {"step_count": len(steps), "steps": steps[:STEP_CAP]}
    if at_step is None:
        return result
    if video is None or out is None:
        raise ToolError("--at-step wants --video and --out as well")
    match = next((s for s in steps if at_step.lower() in _label(s).lower()), None)
    if match is None:
        return {**result, "found": False, "query": at_step}
    from .probe import probe
    from .shot import shot
    at = min(match["end_s"], max(0.0, probe(video)["duration_s"] - 0.05))
    grabbed = shot(video, out, at=at)
    return {**result, "found": True, "query": at_step,
            "step": match, "shot": grabbed}


def _label(step):
    return f"{step['title']} {step.get('selector') or ''}"


def _parse(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith(".trace")]
            if not names:
                raise ToolError("no .trace entries inside — not a Playwright trace zip?")
            events = []
            for name in names:
                for line in z.read(name).decode("utf-8", errors="replace").splitlines():
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        continue
    except zipfile.BadZipFile:
        raise ToolError("not a zip file — expected a Playwright trace.zip")
    befores = {e["callId"]: e for e in events
               if e.get("type") == "before" and "callId" in e and "startTime" in e}
    if not befores:
        raise ToolError("no action events found in trace (unsupported or empty trace)")
    t0 = min(min(e["startTime"] for e in befores.values()),
             min((e["monotonicTime"] for e in events if "monotonicTime" in e),
                 default=float("inf")))
    steps = []
    for e in events:
        if e.get("type") != "after" or e.get("callId") not in befores:
            continue
        b = befores[e["callId"]]
        # 1.3x traces carry apiName; current ones carry class+method (Frame.click)
        title = b.get("apiName") or f"{b.get('class', '?').lower()}.{b.get('method', '?')}"
        step = {
            "title": title,
            "start_s": r4((b["startTime"] - t0) / 1000.0),
            "end_s": r4((e.get("endTime", b["startTime"]) - t0) / 1000.0),
        }
        params = b.get("params") or {}
        if params.get("selector"):
            step["selector"] = params["selector"]
        if params.get("url"):
            step["url"] = params["url"]
        steps.append(step)
    return sorted(steps, key=lambda s: s["start_s"])

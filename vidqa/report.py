"""One-call composite QA verdict.

Composes probe + timing + scenes (+ audio when the file has an audio stream,
+ golden diff when a reference is given) and applies default gate thresholds.
Raw sections stay in the output so an agent can always look past the verdict.
"""
from .probe import probe
from .scenes import scenes
from .timing import timing

DUP_RATIO_MAX = 0.05
STUTTER_EVENTS_MAX = 0
MAX_SILENCE_S = 2.0


def report(path, golden=None, at=None):
    sections = {"probe": probe(path), "timing": timing(path), "scenes": scenes(path)}
    issues = []

    t = sections["timing"]
    for f in t["freezes"]:
        dur = f["duration_s"] if f["duration_s"] is not None else "end"
        issues.append(f"freeze@{f['start_s']}s({dur}s)")
    if t["dup_ratio"] > DUP_RATIO_MAX:
        issues.append(f"dup_ratio={t['dup_ratio']}")
    if t["stutter"]["event_count"] > STUTTER_EVENTS_MAX:
        issues.append(f"stutter_events={t['stutter']['event_count']}")

    if sections["probe"]["audio"] is not None:
        from .audio import audio
        sections["audio"] = audio(path)
        a = sections["audio"]
        if a["clipping_suspected"]:
            issues.append("audio_clipping")
        for s in a["silences"]:
            if s["duration_s"] is not None and s["duration_s"] > MAX_SILENCE_S:
                issues.append(f"silence@{s['start_s']}s({s['duration_s']}s)")

    if golden is not None:
        from .diff import diff
        sections["diff"] = diff(path, golden, at=at)
        if not sections["diff"]["pass"]:
            issues.append("golden_diff_failed")

    sections["verdict"] = {"pass": not issues, "issues": issues}
    return sections

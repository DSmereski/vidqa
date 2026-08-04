"""Write detected events as an .srt subtitle track any video player can show.

Pure composition of the existing detectors — freezes/stutter (timing),
scene cuts (scenes), silences (audio). Point your player at the recording
with this track and the analysis rides along the scrubber.
"""
from .ffutil import ToolError, r4

INSTANT_S = 1.0
EVENT_CAP = 200


def collect_events(path):
    """Detected events as (start_s, end_s, kind, label), sorted (shared with moments)."""
    from .scenes import scenes
    from .timing import timing
    t = timing(path)
    events = []
    for fr in t["freezes"]:
        dur = fr["duration_s"]
        end = fr["start_s"] + (dur if dur is not None else INSTANT_S)
        label = f"freeze {r4(dur)}s" if dur is not None else "freeze (to end)"
        events.append((fr["start_s"], end, "freeze", label))
    for ev in t["stutter"]["events"]:
        events.append((ev["t_s"], ev["t_s"] + INSTANT_S, "stutter",
                       f"stutter {r4(ev['delta_ms'])}ms"))
    for cut in scenes(path)["cuts"]:
        events.append((cut, cut + INSTANT_S, "cut", "scene cut"))
    try:
        from .audio import audio
        silences = audio(path)["silences"]
    except ToolError:
        silences = []  # no audio stream -> simply no audio events
    for sil in silences:
        events.append((sil["start_s"], sil["start_s"] + sil["duration_s"],
                       "silence", f"silence {r4(sil['duration_s'])}s"))
    events.sort(key=lambda e: (e[0], e[1], e[3]))
    return events


def srt(path, out):
    events = collect_events(path)[:EVENT_CAP]
    lines = []
    for i, (start, end, _, label) in enumerate(events, 1):
        lines += [str(i), f"{_ts(start)} --> {_ts(end)}", label, ""]
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    counts = {}
    for _, _, kind, _ in events:
        counts[kind] = counts.get(kind, 0) + 1
    return {"counts": counts, "event_count": len(events), "out": out}


def _ts(seconds):
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

"""One command -> a ticket-ready evidence folder for a moment in a recording."""
import os

from .ffutil import jdump, r4


def bugpack(path, at, out, title=None):
    os.makedirs(out, exist_ok=True)
    from .clip import clip
    from .ocr import ocr
    from .report import report
    from .shot import shot
    from .srt import srt
    rep = report(path)
    duration = rep["probe"]["duration_s"] or at
    frame = os.path.join(out, "frame.png")
    shot(path, frame, at=min(at, max(0.0, duration - 0.05)))
    start = max(0.0, at - 3.0)
    end = min(duration, at + 3.0)
    if end - start < 0.2:
        start, end = 0.0, duration
    clip(path, os.path.join(out, "clip.mp4"), start, end)
    srt(path, os.path.join(out, "events.srt"))
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
        fh.write(jdump(rep))
    issues = rep["verdict"]["issues"]
    lines = [
        f"# {title or os.path.basename(path)}",
        "",
        f"- video: {os.path.basename(path)}",
        f"- at: {r4(at)}s",
        f"- verdict: {'pass' if rep['verdict']['pass'] else 'FAIL'}",
    ]
    lines += [f"  - {issue}" for issue in issues]
    joined = ocr(frame)["joined"]
    if joined:
        lines.append(f"- on-screen text at {r4(at)}s: {joined[:400]}")
    lines += ["", "files: frame.png, clip.mp4, events.srt, report.json", ""]
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    return {
        "at_s": r4(at),
        "files": ["clip.mp4", "events.srt", "frame.png", "report.json", "summary.md"],
        "issues": issues,
        "out": out,
        "title": title or os.path.basename(path),
    }

"""Thin MCP wrapper so non-Claude-Code clients (Hive bots, other harnesses)
get the same vidqa tools over stdio. All heavy lifting stays in the modules."""
from mcp.server import MCPServer

from .ask import FRAMES_DEFAULT, MODEL_DEFAULT
from .ffutil import require_file
from .speech import MODEL_DEFAULT as SPEECH_MODEL_DEFAULT

server = MCPServer("vidqa")


def _given(**kw):
    """Drop unset knobs so the modules' own defaults stay in charge."""
    return {k: v for k, v in kw.items() if v is not None}


@server.tool()
def probe(path: str) -> dict:
    """Container/stream facts for a video: codecs, fps, duration, CFR/VFR."""
    from .probe import probe as impl
    return impl(require_file(path))


@server.tool()
def timing(path: str) -> dict:
    """Frame-timing QA: stutter events, duplicate frames, freezes, percentiles."""
    from .timing import timing as impl
    return impl(require_file(path))


@server.tool()
def diff(candidate: str, golden: str, at: float | None = None,
         ignore: list[list[int]] | None = None,
         ssim_min: float | None = None, cell_max: float | None = None,
         mask_out: str | None = None) -> dict:
    """Compare a frame against a golden image; ignore = [[x,y,w,h], ...] dynamic
    regions; ssim_min/cell_max override the gate thresholds; mask_out writes a
    diff-mask png."""
    from .diff import diff as impl
    return impl(require_file(candidate), require_file(golden), at=at,
                ignore=ignore, mask_out=mask_out,
                **_given(ssim_min=ssim_min, cell_max=cell_max))


@server.tool()
def scenes(path: str, threshold: float | None = None) -> dict:
    """Scene-cut timestamps; threshold = cut sensitivity (default 27)."""
    from .scenes import scenes as impl
    return impl(require_file(path), **_given(threshold=threshold))


@server.tool()
def report(path: str, golden: str | None = None, at: float | None = None) -> dict:
    """One-call composite QA verdict over a video."""
    from .report import report as impl
    if golden is not None:
        require_file(golden)
    return impl(require_file(path), golden=golden, at=at)


@server.tool()
def audio(path: str) -> dict:
    """Audio glitch checks: silences, clipping, volume stats."""
    from .audio import audio as impl
    return impl(require_file(path))


@server.tool()
def when(path: str, text: str | None = None, template: str | None = None,
         step: float = 0.5, threshold: float | None = None) -> dict:
    """Find when given text (OCR) or a template image is visible: intervals in
    seconds; threshold = template match floor (default 0.8)."""
    from .when import when as impl
    if template is not None:
        require_file(template)
    return impl(require_file(path), text=text, template=template, step=step,
                **_given(threshold=threshold))


@server.tool()
def shot(path: str, out: str, at: float | None = None,
         at_text: str | None = None,
         annotate: list[list] | None = None,
         around: float | None = None, gap: float = 0.5,
         zoom: bool = False) -> dict:
    """Extract a frame as PNG evidence (or a before/after pair via around;
    zoom crops the pair to what changed); annotate = [[x,y,w,h] or
    [x,y,w,h,label], ...] boxes."""
    from .shot import shot as impl
    if annotate is not None:
        annotate = [list(a) + [None] * (5 - len(a)) for a in annotate]
    return impl(require_file(path), out, at=at, at_text=at_text,
                annotate=annotate, around=around, gap=gap, zoom=zoom)


@server.tool()
def moments(path: str, text: str | None = None, step: float = 0.5) -> dict:
    """Auto-index chapter markers: freezes, stutter, cuts, blanks, silences (+ a text's first/last)."""
    from .moments import moments as impl
    return impl(require_file(path), text=text, step=step)


@server.tool()
def contrast(path: str, at: float | None = None, min_ratio: float = 4.5) -> dict:
    """Flag low-contrast on-screen text (WCAG-approx accessibility probe)."""
    from .contrast import contrast as impl
    return impl(require_file(path), at=at, min_ratio=min_ratio)


@server.tool()
def locate(path: str, fail_text: str, step: float = 0.5,
           shots: str | None = None) -> dict:
    """Failure auto-locate: last-good + first-bad timestamps (and frames) from the fail text."""
    from .locate import locate as impl
    return impl(require_file(path), fail_text, step=step, shots=shots)


@server.tool()
def judge(path: str, rubric: str, model: str = MODEL_DEFAULT,
          frames: int = FRAMES_DEFAULT) -> dict:
    """Visual smoke review: enum verdicts on a UX rubric file via the local VLM."""
    from .judge import judge as impl
    return impl(require_file(path), require_file(rubric), model=model,
                frames=frames)


@server.tool()
def text(path: str, step: float = 1.0, contains: str | None = None) -> dict:
    """Index every text line the screen showed, with visibility intervals; toasts flagged."""
    from .text import text as impl
    return impl(require_file(path), step=step, contains=contains)


@server.tool()
def redact(path: str, out: str, regions: list[list[int]]) -> dict:
    """Black out [[x,y,w,h], ...] regions (solid fill) so a recording can be shared."""
    from .redact import redact as impl
    return impl(require_file(path), out, regions)


@server.tool()
def strip(path: str, out: str, every: float = 1.0) -> dict:
    """Filmstrip contact-sheet PNG: one glanceable thumbnail grid with timestamps."""
    from .strip import strip as impl
    return impl(require_file(path), out, every=every)


@server.tool()
def clip(path: str, out: str, start: float, end: float) -> dict:
    """Cut a small excerpt (mp4 or gif) of the video for evidence/tickets."""
    from .clip import clip as impl
    return impl(require_file(path), out, start, end)


@server.tool()
def load(path: str, step: float = 0.25, content_by: float | None = None,
         settled_by: float | None = None) -> dict:
    """Loading behavior from video: time to first content and to visual settle; optional deadlines gate."""
    from .load import load as impl
    return impl(require_file(path), step=step, content_by=content_by,
                settled_by=settled_by)


@server.tool()
def bugpack(path: str, at: float, out: str, title: str | None = None) -> dict:
    """Emit a ticket-ready evidence folder (frame, clip, srt, report, summary) for a moment."""
    from .bugpack import bugpack as impl
    return impl(require_file(path), at, out, title=title)


@server.tool()
def srt(path: str, out: str) -> dict:
    """Write detected events (freezes, stutter, scene cuts, silences) as an .srt subtitle track."""
    from .srt import srt as impl
    return impl(require_file(path), out)


@server.tool()
def rundiff(a: str, b: str, step: float = 0.5, threshold: int = 8,
            shots: str | None = None, ignore: list[list[int]] | None = None,
            trace_a: str | None = None, trace_b: str | None = None,
            md: str | None = None) -> dict:
    """Compare two runs of the same test: by clock, or by Playwright steps when traces given."""
    from .rundiff import rundiff as impl
    for tr in (trace_a, trace_b):
        if tr is not None:
            require_file(tr)
    result = impl(require_file(a), require_file(b), step=step, threshold=threshold,
                  shots=shots, ignore=ignore, trace_a=trace_a, trace_b=trace_b)
    if md is not None:
        from .md import rundiff_md
        result["md"] = rundiff_md(md, result, a, b)
    return result


@server.tool()
def ci(path: str, rules: str, step: float = 0.5, md: str | None = None) -> dict:
    """Evaluate a QA rules file (expect/forbid text, templates, freezes, blanks) against a recording."""
    from .ci import ci as impl
    result = impl(require_file(path), require_file(rules), step=step)
    if md is not None:
        from .md import ci_md
        result["md"] = ci_md(md, result, path)
    return result


@server.tool()
def trace(path: str, video: str | None = None, at_step: str | None = None,
          out: str | None = None) -> dict:
    """Playwright trace.zip -> step timeline; optionally grab the frame where a step completed."""
    from .trace import trace as impl
    if video is not None:
        require_file(video)
    return impl(require_file(path), video=video, at_step=at_step, out=out)


@server.tool()
def record_android(cmd: str, out: str, serial: str | None = None) -> dict:
    """Record the Android device screen (adb screenrecord) while a shell command runs."""
    from .record_android import record_android as impl
    return impl(cmd, out, serial=serial)


@server.tool()
def live(process: str, seconds: int = 10) -> dict:
    """Capture real frametimes of a RUNNING process via PresentMon ETW (Windows)."""
    from .live import live as impl
    return impl(process, seconds=seconds)


@server.tool()
def speech(path: str, model: str = SPEECH_MODEL_DEFAULT, full: bool = False,
           find: str | None = None) -> dict:
    """Transcribe spoken audio (faster-whisper, local CPU); find = phrase to timestamp."""
    from .speech import speech as impl
    return impl(require_file(path), model=model, full=full, find=find)


@server.tool()
def ocr(path: str, at: float | None = None) -> dict:
    """Read text off a frame (RapidOCR, local CPU)."""
    from .ocr import ocr as impl
    return impl(require_file(path), at=at)


@server.tool()
def find(path: str, template: str, at: float | None = None,
         threshold: float | None = None) -> dict:
    """Locate a known UI element in a frame via template matching;
    threshold = match floor (default 0.8)."""
    from .find import find as impl
    return impl(require_file(path), require_file(template), at=at,
                **_given(threshold=threshold))


@server.tool()
def ask(path: str, question: str, enum: list[str] | None = None,
        model: str = MODEL_DEFAULT, frames: int = FRAMES_DEFAULT) -> dict:
    """Ask a local VLM a question about a video (fully on-device)."""
    from .ask import ask as impl
    return impl(require_file(path), question, model=model, frames=frames, enum=enum)


def main():
    server.run()


if __name__ == "__main__":
    main()

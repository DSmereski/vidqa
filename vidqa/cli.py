"""vidqa: local, deterministic video QA. Compact JSON on stdout.

Exit codes: 0 = ok (gate passed), 1 = gate failed, 2 = error.
"""
import argparse
import sys

from .ffutil import ToolError, jdump, require_file


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vidqa", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="container/stream facts")
    p.add_argument("video")

    p = sub.add_parser("timing", help="frame timing: stutter, dups, freezes")
    p.add_argument("video")

    p = sub.add_parser("diff", help="compare a frame (or video frame) against a golden image")
    p.add_argument("candidate")
    p.add_argument("--golden", required=True)
    p.add_argument("--at", type=float, default=None, help="timestamp if candidate is a video")
    p.add_argument("--mask-out", default=None, help="write a diff-mask png here")
    p.add_argument("--ssim-min", type=float, default=None, help="default 0.95")
    p.add_argument("--cell-max", type=float, default=None, help="default 25.0")

    p = sub.add_parser("scenes", help="scene cut timestamps")
    p.add_argument("video")
    p.add_argument("--threshold", type=float, default=27.0)

    p = sub.add_parser("report", help="one-call composite QA verdict")
    p.add_argument("video")
    p.add_argument("--golden", default=None)
    p.add_argument("--at", type=float, default=None)

    p = sub.add_parser("audio", help="silences, clipping, volume stats")
    p.add_argument("video")

    p = sub.add_parser("when", help="find when text or a template is visible")
    p.add_argument("video")
    p.add_argument("text", nargs="?", default=None)
    p.add_argument("--template", default=None, help="element image instead of text")
    p.add_argument("--step", type=float, default=None, help="sample interval s, default 0.5")
    p.add_argument("--threshold", type=float, default=None, help="template floor, default 0.8")

    p = sub.add_parser("shot", help="extract a frame (optionally cropped) as png evidence")
    p.add_argument("video")
    p.add_argument("--out", required=True)
    p.add_argument("--at", type=float, default=None)
    p.add_argument("--at-text", default=None, help="frame where this text is visible")
    p.add_argument("--crop", default=None, help="x,y,w,h")
    p.add_argument("--step", type=float, default=None, help="--at-text sample interval")

    p = sub.add_parser("strip", help="filmstrip contact-sheet png of the whole video")
    p.add_argument("video")
    p.add_argument("--out", required=True)
    p.add_argument("--every", type=float, default=None, help="seconds per thumb, default 1.0")

    p = sub.add_parser("clip", help="cut a small excerpt (mp4 or gif) for tickets")
    p.add_argument("video")
    p.add_argument("--out", required=True)
    p.add_argument("--from", dest="start", type=float, required=True)
    p.add_argument("--to", dest="end", type=float, required=True)

    p = sub.add_parser("srt", help="write detected events (freezes, cuts, stutter, silences) as an .srt track")
    p.add_argument("video")
    p.add_argument("--out", required=True)

    p = sub.add_parser("rundiff", help="compare two recordings of the same test; exit 1 on divergence")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--step", type=float, default=None, help="sample interval s, default 0.5")
    p.add_argument("--threshold", type=int, default=None, help="pHash distance floor, default 8")
    p.add_argument("--shots", default=None, help="dir to write the first-divergence frame pair")

    p = sub.add_parser("ci", help="evaluate a rules file against a recording; one exit code")
    p.add_argument("video")
    p.add_argument("--rules", required=True, help="rules json (see vidqa.ci docstring)")
    p.add_argument("--step", type=float, default=None, help="scan interval s, default 0.5")

    p = sub.add_parser("trace", help="Playwright trace.zip -> step timeline (+ frame at a step)")
    p.add_argument("tracezip")
    p.add_argument("--video", default=None, help="the run's video, for --at-step")
    p.add_argument("--at-step", default=None, help="grab the frame where this step completed")
    p.add_argument("--out", default=None, help="png path for --at-step")

    p = sub.add_parser("record-android",
                       help="record the device screen while a command runs (adb); exits 1 if the command fails")
    p.add_argument("--while", dest="cmd_while", required=True,
                   help="shell command to run during the recording")
    p.add_argument("--out", required=True)
    p.add_argument("--serial", default=None, help="adb device serial")

    p = sub.add_parser("speech", help="transcribe speech (faster-whisper, local CPU)")
    p.add_argument("video")
    p.add_argument("--model", default=None, help="default large-v3-turbo; tiny/base are faster")
    p.add_argument("--expect", default=None,
                   help="exit 1 unless the transcript contains this (case-insensitive)")
    p.add_argument("--full", action="store_true", help="include segments, no text cap")

    p = sub.add_parser("ocr", help="read text off a frame")
    p.add_argument("video")
    p.add_argument("--at", type=float, default=None)

    p = sub.add_parser("find", help="locate a template image in a frame")
    p.add_argument("video")
    p.add_argument("--template", required=True)
    p.add_argument("--at", type=float, default=None)
    p.add_argument("--threshold", type=float, default=None, help="default 0.8")

    p = sub.add_parser("ask", help="ask a local VLM about the video (fully on-device)")
    p.add_argument("video")
    p.add_argument("question")
    p.add_argument("--model", default=None, help="default qwen3-vl:8b")
    p.add_argument("--frames", type=int, default=None, help="default 6")
    p.add_argument("--enum", default=None, help="comma-separated allowed answers")
    p.add_argument("--expect", default=None, help="exit 1 unless the answer equals this")

    p = sub.add_parser("live", help="capture live frametimes of a running process (PresentMon)")
    p.add_argument("process", help="process name, e.g. mygame.exe")
    p.add_argument("--seconds", type=int, default=10)
    p.add_argument("--presentmon", default=None, help="path to PresentMon exe")

    args = parser.parse_args(argv)
    try:
        result, code = _dispatch(args)
    except ToolError as exc:
        print(f"vidqa: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # single boundary: a crash must never read as exit 1 = "gate failed"
        print(f"vidqa: internal error: {exc}", file=sys.stderr)
        return 2
    print(jdump(result))
    return code


def _dispatch(args):
    for attr in ("video", "candidate", "golden", "template", "a", "b"):
        path = getattr(args, attr, None)
        if path is not None:
            require_file(path)

    if args.cmd == "probe":
        from .probe import probe
        return probe(args.video), 0
    if args.cmd == "timing":
        from .timing import timing
        return timing(args.video), 0
    if args.cmd == "diff":
        from .diff import diff
        result = diff(
            args.candidate, args.golden, at=args.at, mask_out=args.mask_out,
            **_given(ssim_min=args.ssim_min, cell_max=args.cell_max),
        )
        return result, 0 if result["pass"] else 1
    if args.cmd == "scenes":
        from .scenes import scenes
        return scenes(args.video, threshold=args.threshold), 0
    if args.cmd == "report":
        from .report import report
        result = report(args.video, golden=args.golden, at=args.at)
        return result, 0 if result["verdict"]["pass"] else 1
    if args.cmd == "audio":
        from .audio import audio
        return audio(args.video), 0
    if args.cmd == "when":
        from .when import when
        result = when(
            args.video, text=args.text, template=args.template,
            **_given(step=args.step, threshold=args.threshold),
        )
        return result, 0 if result["found"] else 1
    if args.cmd == "shot":
        from .shot import shot
        crop = None
        if args.crop is not None:
            parts = args.crop.split(",")
            if len(parts) != 4 or not all(p.strip().lstrip("-").isdigit() for p in parts):
                raise ToolError("--crop wants four integers: x,y,w,h")
            crop = [int(p) for p in parts]
        result = shot(
            args.video, args.out, at=args.at, at_text=args.at_text, crop=crop,
            **_given(step=args.step),
        )
        return result, 0 if result["found"] else 1
    if args.cmd == "strip":
        from .strip import strip
        return strip(args.video, args.out, **_given(every=args.every)), 0
    if args.cmd == "clip":
        from .clip import clip
        return clip(args.video, args.out, args.start, args.end), 0
    if args.cmd == "srt":
        from .srt import srt
        return srt(args.video, args.out), 0
    if args.cmd == "rundiff":
        from .rundiff import rundiff
        result = rundiff(
            args.a, args.b, shots=args.shots,
            **_given(step=args.step, threshold=args.threshold),
        )
        return result, 1 if result["diverged"] else 0
    if args.cmd == "ci":
        from .ci import ci
        require_file(args.rules)
        result = ci(args.video, args.rules, **_given(step=args.step))
        return result, 0 if result["pass"] else 1
    if args.cmd == "trace":
        from .trace import trace
        require_file(args.tracezip)
        result = trace(args.tracezip, video=args.video,
                       at_step=args.at_step, out=args.out)
        return result, 0 if result.get("found", True) else 1
    if args.cmd == "record-android":
        from .record_android import record_android
        result = record_android(args.cmd_while, args.out, serial=args.serial)
        return result, 0 if result["cmd_exit"] == 0 else 1
    if args.cmd == "speech":
        from .speech import speech
        result = speech(
            args.video, expect=args.expect, full=args.full,
            **_given(model=args.model),
        )
        return result, 0 if result.get("expect_found", True) else 1
    if args.cmd == "ocr":
        from .ocr import ocr
        return ocr(args.video, at=args.at), 0
    if args.cmd == "find":
        from .find import find
        result = find(
            args.video, args.template, at=args.at,
            **_given(threshold=args.threshold),
        )
        return result, 0 if result["found"] else 1
    if args.cmd == "ask":
        from .ask import ask
        enum = None
        if args.enum is not None:
            enum = [e.strip() for e in args.enum.split(",") if e.strip()]
            if not enum:
                raise ToolError("--enum needs at least one non-empty value")
        result = ask(
            args.video, args.question, enum=enum,
            **_given(model=args.model, frames=args.frames),
        )
        code = 1 if args.expect is not None and result["answer"] != args.expect else 0
        return result, code
    from .live import live
    return live(args.process, seconds=args.seconds, presentmon=args.presentmon), 0


def _given(**kwargs):
    """Only pass through flags the user actually set, so module defaults rule."""
    return {k: v for k, v in kwargs.items() if v is not None}


if __name__ == "__main__":
    sys.exit(main())

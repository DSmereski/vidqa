"""vidqa: local, deterministic video QA. Compact JSON on stdout.

Exit codes: 0 = ok (gate passed), 1 = gate failed, 2 = error.
"""
import argparse
import os
import sys

from .ffutil import ToolError, jdump


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
    for attr in ("video", "candidate", "golden"):
        path = getattr(args, attr, None)
        if path is not None and not os.path.exists(path):
            raise ToolError(f"file not found: {path}")
    if args.cmd == "probe":
        from .probe import probe
        return probe(args.video), 0
    if args.cmd == "timing":
        from .timing import timing
        return timing(args.video), 0
    if args.cmd == "diff":
        from .diff import diff
        opts = {}
        if args.ssim_min is not None:
            opts["ssim_min"] = args.ssim_min
        if args.cell_max is not None:
            opts["cell_max"] = args.cell_max
        result = diff(
            args.candidate, args.golden, at=args.at, mask_out=args.mask_out, **opts,
        )
        return result, 0 if result["pass"] else 1
    from .scenes import scenes
    return scenes(args.video, threshold=args.threshold), 0


if __name__ == "__main__":
    sys.exit(main())

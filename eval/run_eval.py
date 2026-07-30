"""CP4 verifier: known-answer eval for `vidqa ask` on synthetic clips.

Generates media once into eval/_media, runs every case N times, scores exact
enum matches, checks answers are identical across runs, and reports latency.
Exit 0 iff every run scores >= PASS_MIN and every case is run-consistent.

Usage: python eval/run_eval.py [--runs 3] [--model qwen3-vl:8b]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vidqa.ask import ask  # noqa: E402

PASS_MIN = 5
SIZE = "640x360"
DRAW = "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':fontsize=64:fontcolor=white:x=80:y=140:text="

CASES = [
    ("red.mp4", "What is the dominant color of the video?",
     ["red", "green", "blue"], "red"),
    ("bars.mp4", "Does the video show a TV test pattern with colored vertical bars?",
     ["yes", "no"], "yes"),
    ("gameover.mp4", "Does the text 'GAME OVER' appear in the video?",
     ["yes", "no"], "yes"),
    ("black.mp4", "Is the video almost entirely black?",
     ["yes", "no"], "yes"),
    ("motion.mp4", "Do all frames look identical, meaning nothing moves or changes?",
     ["yes", "no"], "no"),
    ("score.mp4", "What number appears after the word SCORE?",
     ["12345", "54321", "99999"], "12345"),
]

SOURCES = {
    "red.mp4": ["-f", "lavfi", "-i", f"color=red:duration=2:size={SIZE}:rate=25"],
    "bars.mp4": ["-f", "lavfi", "-i", f"smptebars=duration=2:size={SIZE}:rate=25"],
    "black.mp4": ["-f", "lavfi", "-i", f"color=black:duration=2:size={SIZE}:rate=25"],
    "motion.mp4": ["-f", "lavfi", "-i", f"testsrc2=duration=2:size={SIZE}:rate=25"],
    "gameover.mp4": ["-f", "lavfi", "-i", f"color=black:duration=2:size={SIZE}:rate=25",
                     "-vf", DRAW + "'GAME OVER'"],
    "score.mp4": ["-f", "lavfi", "-i", f"color=black:duration=2:size={SIZE}:rate=25",
                  "-vf", DRAW + "'SCORE 12345'"],
}


def build_media(root):
    root.mkdir(parents=True, exist_ok=True)
    for name, srcargs in SOURCES.items():
        out = root / name
        if out.exists():
            continue
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *srcargs,
             "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(out)],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="qwen3-vl:8b")
    parser.add_argument("--frames", type=int, default=4)
    args = parser.parse_args()

    media = Path(__file__).resolve().parent / "_media"
    build_media(media)

    answers = {name: [] for name, *_ in CASES}
    latencies = []
    scores = []
    for run in range(args.runs):
        correct = 0
        for name, question, enum, expected in CASES:
            t0 = time.perf_counter()
            result = ask(str(media / name), question,
                         model=args.model, frames=args.frames, enum=enum)
            latencies.append(time.perf_counter() - t0)
            answers[name].append(result["answer"])
            ok = result["answer"] == expected
            correct += ok
            print(f"run{run + 1} {name}: {result['answer']!r} "
                  f"(want {expected!r}) {'OK' if ok else 'MISS'} "
                  f"[{latencies[-1]:.1f}s]")
        scores.append(correct)

    consistent = all(len(set(a)) == 1 for a in answers.values())
    summary = {
        "model": args.model,
        "runs": args.runs,
        "scores": scores,
        "total_cases": len(CASES),
        "pass_min": PASS_MIN,
        "consistent_across_runs": consistent,
        "mean_latency_s": round(sum(latencies) / len(latencies), 2),
        "max_latency_s": round(max(latencies), 2),
    }
    print(json.dumps(summary))
    ok = consistent and all(s >= PASS_MIN for s in scores)
    print(f"EVAL {'PASS' if ok else 'FAIL'}: scores={scores}/{len(CASES)} "
          f"consistent={consistent}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

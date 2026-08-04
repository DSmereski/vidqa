"""Markdown report files for CI/PR comments (--md on ci and rundiff).

stdout stays compact JSON — the markdown goes to a file so a pipeline can
post it verbatim as a PR comment.
"""
import json
import os


def write_md(path, lines):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def ci_md(out, result, video):
    verdict = "✅ PASS" if result["pass"] else "❌ FAIL"
    lines = [
        f"# vidqa ci — {verdict}",
        "",
        f"`{os.path.basename(video)}` · step {result['step_s']}s",
        "",
        "| rule | result | detail |",
        "|---|---|---|",
    ]
    for r in result["rules"]:
        rule = {k: v for k, v in r["rule"].items() if k != "type"}
        desc = r["rule"]["type"]
        if rule:
            desc += " " + json.dumps(rule, sort_keys=True)
        detail = ", ".join(f"{k}={v}" for k, v in sorted(r["detail"].items()))
        mark = "✅" if r["pass"] else "❌"
        lines.append(f"| {_cell(desc)} | {mark} | {_cell(detail)} |")
    return write_md(out, lines)


def rundiff_md(out, result, a, b):
    verdict = "❌ diverged" if result["diverged"] else "✅ same"
    lines = [
        f"# vidqa rundiff — {verdict}",
        "",
        f"`{os.path.basename(a)}` vs `{os.path.basename(b)}`",
        "",
    ]
    if result.get("mode") == "steps":
        if result["step_mismatch"]:
            m = result["step_mismatch"]
            lines.append(f"- step sequence mismatch at #{m['index']}: "
                         f"`{_cell(m['a'])}` vs `{_cell(m['b'])}`")
        lines += ["", "| step | a_s | b_s | distance | diverged |", "|---|---|---|---|---|"]
        for s in result["steps"]:
            mark = "❌" if s["diverged"] else "✅"
            lines.append(f"| {_cell(s['title'])} | {s['a_s']} | {s['b_s']} "
                         f"| {s['distance']} | {mark} |")
    else:
        first = result["first_divergence_s"]
        lines.append(f"- first divergence: "
                     + (f"**{first}s**" if first is not None else "none"))
        lines.append(f"- sampled {result['sampled']} pairs @ {result['step_s']}s, "
                     f"threshold {result['threshold']}, "
                     f"mean distance {result['mean_distance']}")
        if result["divergences"]:
            lines += ["", "| at_s | distance |", "|---|---|"]
            lines += [f"| {d['at_s']} | {d['distance']} |"
                      for d in result["divergences"]]
    if result.get("shots"):
        lines.append("")
        lines.append("shots: " + ", ".join(os.path.basename(p)
                                           for p in result["shots"]))
    return write_md(out, lines)


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")

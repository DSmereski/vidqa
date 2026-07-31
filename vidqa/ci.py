"""Rules-file CI gate: evaluate expectations against a recording, one exit code.

Rules file shape: {"rules": [{"type": ..., ...}, ...]} with types:
  expect_text     {text, by_s?}        text must become visible (by a deadline)
  forbid_text     {words? | builtin: "error_pages"}   words must never appear
  expect_template {file, by_s?}        element image must become visible
  max_freeze_s    {seconds}            no static-content freeze longer than this
  no_blank_frames {}                   no near-uniform (blank) frame
"""
import json
import os
import tempfile

import cv2

from .diff import load_frame
from .ffutil import ToolError, r4, run

STEP_DEFAULT = 0.5
TEMPLATE_THRESHOLD = 0.8
BLANK_STD = 3.0
ERROR_PAGE_WORDS = [
    "internal server error", "404 not found", "502 bad gateway",
    "503 service unavailable", "traceback (most recent call last)",
    "unhandled exception", "err_connection", "err_name_not_resolved",
    "cannot get /",
]
SCAN_TYPES = {"expect_text", "forbid_text", "expect_template", "no_blank_frames"}


def ci(path, rules_file, step=STEP_DEFAULT):
    rules = _load_rules(rules_file)
    tpl_rules = [r for r in rules if r["type"] == "expect_template"]
    samples = []
    if any(r["type"] in SCAN_TYPES for r in rules):
        samples = _scan(path, rules, tpl_rules, step)
    freezes = None
    if any(r["type"] == "max_freeze_s" for r in rules):
        from .timing import timing
        freezes = timing(path)["freezes"]
    results = [_evaluate(rule, samples, freezes, tpl_rules) for rule in rules]
    return {
        "pass": all(r["pass"] for r in results),
        "rules": results,
        "step_s": r4(step),
    }


def _load_rules(rules_file):
    try:
        with open(rules_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ToolError(f"rules file unreadable or not valid JSON: {exc}")
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        raise ToolError('rules file wants {"rules": [ ... ]} with at least one rule')
    for rule in rules:
        kind = rule.get("type") if isinstance(rule, dict) else None
        if kind == "expect_text" and rule.get("text"):
            continue
        if kind == "forbid_text" and (rule.get("words") or rule.get("builtin") == "error_pages"):
            continue
        if kind == "expect_template" and rule.get("file"):
            if not os.path.isfile(rule["file"]):
                raise ToolError(f"expect_template file not found: {rule['file']}")
            continue
        if kind == "max_freeze_s" and isinstance(rule.get("seconds"), (int, float)):
            continue
        if kind == "no_blank_frames":
            continue
        raise ToolError(f"invalid rule: {json.dumps(rule, sort_keys=True)}")
    return rules


def _scan(path, rules, tpl_rules, step):
    if step <= 0:
        raise ToolError("--step must be positive")
    want_text = any(r["type"] in ("expect_text", "forbid_text") for r in rules)
    templates = [load_frame(r["file"]) for r in tpl_rules]
    samples = []
    with tempfile.TemporaryDirectory() as td:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", path, "-vf", f"fps={1.0 / step}",
             "-start_number", "0", os.path.join(td, "f%06d.png")])
        names = sorted(os.listdir(td))
        if not names:
            raise ToolError("no frames sampled (empty or audio-only video?)")
        for i, name in enumerate(names):
            frame = cv2.imread(os.path.join(td, name))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            text = ""
            if want_text:
                from .ocr import scan_text
                text = scan_text(frame).lower()
            tpl_hits = []
            for tpl in templates:
                if tpl.shape[0] > frame.shape[0] or tpl.shape[1] > frame.shape[1]:
                    raise ToolError("expect_template image larger than the video frame")
                _, best, _, _ = cv2.minMaxLoc(
                    cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
                tpl_hits.append(bool(best >= TEMPLATE_THRESHOLD))
            samples.append({
                "t": i * step,
                "text": text,
                "blank": bool(gray.std() < BLANK_STD),
                "tpl_hits": tpl_hits,
            })
    return samples


def _evaluate(rule, samples, freezes, tpl_rules):
    kind = rule["type"]
    if kind in ("expect_text", "expect_template"):
        if kind == "expect_text":
            needle = rule["text"].lower()
            hits = [s["t"] for s in samples if needle in s["text"]]
        else:
            idx = tpl_rules.index(rule)
            hits = [s["t"] for s in samples if s["tpl_hits"][idx]]
        by = rule.get("by_s")
        ok = bool(hits) and (by is None or hits[0] <= by)
        detail = {"first_s": r4(hits[0])} if hits else {"reason": "never visible"}
        if hits and not ok:
            detail["reason"] = f"first visible at {r4(hits[0])}s, after by_s={by}"
        return {"rule": rule, "pass": ok, "detail": detail}
    if kind == "forbid_text":
        words = rule.get("words") or ERROR_PAGE_WORDS
        for s in samples:
            for word in words:
                if word.lower() in s["text"]:
                    return {"rule": rule, "pass": False,
                            "detail": {"word": word, "at_s": r4(s["t"])}}
        return {"rule": rule, "pass": True, "detail": {}}
    if kind == "max_freeze_s":
        limit = float(rule["seconds"])
        worst = 0.0
        unbounded = False
        for fr in freezes:
            if fr["duration_s"] is None:
                unbounded = True
            else:
                worst = max(worst, fr["duration_s"])
        ok = not unbounded and worst <= limit
        return {"rule": rule, "pass": ok,
                "detail": {"worst_s": None if unbounded else r4(worst)}}
    blanks = [s["t"] for s in samples if s["blank"]]
    return {"rule": rule, "pass": not blanks,
            "detail": {"first_blank_s": r4(blanks[0])} if blanks else {}}

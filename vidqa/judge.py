"""Automated visual smoke review: a UX rubric judged by the local VLM.

Rubric file shape: {"items": [{"id": ..., "question": ..., "options": [...],
"fail": ...}, ...]}. Each item is one enum-constrained `ask` over the same
sampled frames; the item fails when the model answers the `fail` option.
Enum answers are argmax-stable at temperature 0 (same guarantee as `ask`).
"""
import json

from .ask import FRAMES_DEFAULT, MODEL_DEFAULT, ask
from .ffutil import ToolError

ITEM_CAP = 20


def judge(path, rubric_file, model=MODEL_DEFAULT, frames=FRAMES_DEFAULT):
    items = _load_rubric(rubric_file)
    results = []
    for item in items:
        answered = ask(path, item["question"], model=model, frames=frames,
                       enum=item["options"])
        results.append({
            "answer": answered["answer"],
            "confidence": answered["confidence"],
            "id": item["id"],
            "pass": answered["answer"] != item["fail"],
            "question": item["question"],
        })
    return {
        "pass": all(r["pass"] for r in results),
        "items": results,
        "model": model,
        "frames": frames,
    }


def _load_rubric(rubric_file):
    try:
        with open(rubric_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ToolError(f"rubric file unreadable or not valid JSON: {exc}")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ToolError('rubric wants {"items": [ ... ]} with at least one item')
    if len(items) > ITEM_CAP:
        raise ToolError(f"rubric has {len(items)} items; cap is {ITEM_CAP}")
    for item in items:
        if not isinstance(item, dict) or not item.get("id") or not item.get("question"):
            raise ToolError(f"rubric item needs id and question: {json.dumps(item)}")
        options = item.get("options")
        if not isinstance(options, list) or len(options) < 2 \
                or not all(isinstance(o, str) and o for o in options):
            raise ToolError(f"item '{item['id']}': options wants >= 2 strings")
        if item.get("fail") not in options:
            raise ToolError(f"item '{item['id']}': fail must be one of options")
    return items

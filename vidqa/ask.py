"""Semantic video Q&A via a local VLM (Ollama structured outputs).

Frames are sampled uniformly and sent as images to a schema-constrained chat
call at temperature 0. Gate automated logic on `answer` (enum-constrain it
with --enum) — enums are argmax-stable under GPU float noise; `evidence`
prose is best-effort only, never byte-stable.
"""
import base64
import json
import os
import tempfile
import urllib.error
import urllib.request

from .ffutil import ToolError, run, safe_path
from .probe import probe

OLLAMA_URL = os.environ.get("VIDQA_OLLAMA", "http://127.0.0.1:11434")
MODEL_DEFAULT = "qwen3-vl:8b"
FRAMES_DEFAULT = 6
FRAME_WIDTH = 854   # downscale before sending: plenty for UI reading, cheap on vision tokens
TIMEOUT_S = 300
EVIDENCE_CAP = 400
ANSWER_CAP = 200


def ask(path, question, model=MODEL_DEFAULT, frames=FRAMES_DEFAULT, enum=None):
    if frames < 1:
        raise ToolError("frames must be >= 1")
    images = _sample_frames(path, frames)
    answer_schema = (
        {"type": "string", "enum": list(enum)} if enum else {"type": "string"}
    )
    schema = {
        "type": "object",
        "properties": {
            "answer": answer_schema,
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "evidence": {"type": "string"},
        },
        "required": ["answer", "confidence", "evidence"],
    }
    prompt = (
        f"You are analyzing {len(images)} frames sampled in chronological order "
        f"from one video. Answer strictly from what is visible in the frames.\n"
        f"Question: {question}"
    )
    if enum:
        prompt += f"\nYour answer MUST be exactly one of: {', '.join(enum)}."
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": images}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0, "seed": 42},
    }
    body = _ollama_chat(payload)
    try:
        parsed = json.loads(body["message"]["content"])
    except (KeyError, TypeError, ValueError):
        raise ToolError(f"unexpected ollama response shape: {str(body)[:200]}")
    answer = parsed.get("answer")
    if isinstance(answer, str):
        answer = answer[:ANSWER_CAP]
    return {
        "answer": answer,
        "confidence": parsed.get("confidence"),
        "evidence": str(parsed.get("evidence", ""))[:EVIDENCE_CAP],
        "model": model,
        "frames_used": len(images),
    }


def _ollama_chat(payload):
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        raise ToolError(f"ollama returned HTTP {exc.code}: {detail}")
    except OSError as exc:
        raise ToolError(f"ollama not reachable at {OLLAMA_URL}: {exc}")


def _sample_frames(path, n):
    duration = probe(path)["duration_s"]
    if duration is None or duration <= 0:
        raise ToolError(f"cannot sample frames: duration of {path} is {duration}")
    images = []
    for i in range(n):
        t = duration * (i + 0.5) / n
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        try:
            run(["ffmpeg", "-hide_banner", "-y", "-ss", f"{t:.3f}",
                 "-i", safe_path(path), "-frames:v", "1",
                 "-vf", f"scale='min({FRAME_WIDTH},iw)':-2", "-q:v", "4", tmp.name])
            with open(tmp.name, "rb") as fh:
                data = fh.read()
            if not data:
                raise ToolError(f"no frame extracted at {t:.3f}s from {path}")
            images.append(base64.b64encode(data).decode())
        finally:
            os.unlink(tmp.name)
    return images

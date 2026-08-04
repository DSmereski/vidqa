import json
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import vidqa.ask
from vidqa.ffutil import ToolError
from vidqa.judge import judge


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def _ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=3)
        return True
    except OSError:
        return False


def _rubric(tmp_path, items):
    p = tmp_path / "rubric.json"
    p.write_text(json.dumps({"items": items}), encoding="utf-8")
    return str(p)


class _StubHandler(BaseHTTPRequestHandler):
    answer = "yes"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        content = json.dumps({"answer": type(self).answer,
                              "confidence": "high", "evidence": "stub"})
        self.wfile.write(json.dumps(
            {"message": {"content": content}}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_ollama(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(vidqa.ask, "OLLAMA_URL", f"http://127.0.0.1:{server.server_port}")
    yield _StubHandler
    server.shutdown()


def test_judge_pass_and_fail_verdicts(media, tmp_path, stub_ollama):
    stub_ollama.answer = "yes"
    rubric = _rubric(tmp_path, [
        {"id": "spinner-gone", "question": "q1",
         "options": ["yes", "no"], "fail": "no"},
        {"id": "no-truncation", "question": "q2",
         "options": ["yes", "no"], "fail": "yes"},
    ])
    result = judge(str(media["red"]), rubric, frames=1)
    assert result["pass"] is False
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["spinner-gone"]["pass"] is True
    assert by_id["no-truncation"]["pass"] is False
    assert by_id["no-truncation"]["answer"] == "yes"


def test_judge_all_pass(media, tmp_path, stub_ollama):
    stub_ollama.answer = "no"
    rubric = _rubric(tmp_path, [{"id": "a", "question": "q",
                                 "options": ["yes", "no"], "fail": "yes"}])
    result = judge(str(media["red"]), rubric, frames=1)
    assert result["pass"] is True and result["items"][0]["confidence"] == "high"


@pytest.mark.parametrize("items", [
    "not-a-list",
    [],
    [{"id": "x", "question": "q", "options": ["only-one"], "fail": "only-one"}],
    [{"id": "x", "question": "q", "options": ["a", "b"], "fail": "c"}],
    [{"question": "q", "options": ["a", "b"], "fail": "a"}],
])
def test_judge_invalid_rubric_errors(media, tmp_path, items):
    with pytest.raises(ToolError):
        judge(str(media["red"]), _rubric(tmp_path, items), frames=1)


def test_judge_cli_fail_exits_1(media, tmp_path, stub_ollama):
    # CLI runs in a subprocess, so point it at the stub via the env var
    import os
    stub_ollama.answer = "yes"
    rubric = _rubric(tmp_path, [{"id": "a", "question": "q",
                                 "options": ["yes", "no"], "fail": "yes"}])
    env = dict(os.environ, VIDQA_OLLAMA=vidqa.ask.OLLAMA_URL)
    proc = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "judge", str(media["red"]),
         "--rubric", rubric, "--frames", "1"],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["pass"] is False


@pytest.mark.skipif(not _ollama_up(), reason="ollama not running")
def test_judge_live_red_video(media, tmp_path):
    rubric = _rubric(tmp_path, [
        {"id": "is-red", "question": "Is the video predominantly red?",
         "options": ["yes", "no"], "fail": "no"},
        {"id": "is-blue", "question": "Is the video predominantly blue?",
         "options": ["yes", "no"], "fail": "yes"},
    ])
    result = judge(str(media["red"]), rubric, frames=2)
    assert result["pass"] is True
    assert all(i["pass"] for i in result["items"])

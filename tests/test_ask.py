import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import vidqa.ask
from vidqa.ask import ask
from vidqa.ffutil import ToolError


def _ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=3)
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="ollama not running")
def test_ask_enum_answer(media):
    result = ask(
        str(media["red"]), "What is the dominant color of the video?",
        frames=2, enum=["red", "green", "blue"],
    )
    assert result["answer"] == "red"
    assert result["frames_used"] == 2
    assert result["model"] == "qwen3-vl:8b"


class _StubHandler(BaseHTTPRequestHandler):
    status = 200
    body = b"{}"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_ollama(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(vidqa.ask, "OLLAMA_URL", f"http://127.0.0.1:{server.server_port}")
    yield _StubHandler
    server.shutdown()


def test_http_error_surfaced_with_status(media, stub_ollama):
    stub_ollama.status = 404
    stub_ollama.body = b'{"error":"model not found"}'
    with pytest.raises(ToolError, match="HTTP 404"):
        ask(str(media["red"]), "q", frames=1, enum=["yes", "no"])


def test_malformed_response_is_an_error(media, stub_ollama):
    stub_ollama.status = 200
    stub_ollama.body = b'{"unexpected": true}'
    with pytest.raises(ToolError, match="unexpected ollama response shape"):
        ask(str(media["red"]), "q", frames=1, enum=["yes", "no"])


def test_ollama_down_is_an_error(media, monkeypatch):
    monkeypatch.setattr(vidqa.ask, "OLLAMA_URL", "http://127.0.0.1:9")
    with pytest.raises(ToolError, match="not reachable"):
        ask(str(media["red"]), "q", frames=1, enum=["yes", "no"])


def test_zero_frames_rejected(media):
    with pytest.raises(ToolError, match="frames must be"):
        ask(str(media["red"]), "q", frames=0)

import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
from types import SimpleNamespace

import pytest


def test_mcp_stdio_roundtrip(media):
    proc = subprocess.Popen(
        [sys.executable, "-m", "vidqa.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    responses = {}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "id" in msg:
                responses[msg["id"]] = msg

    threading.Thread(target=reader, daemon=True).start()

    def send(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                         "clientInfo": {"name": "test", "version": "0"}}})
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "probe",
                         "arguments": {"path": str(media["clean"])}}})
        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "probe",
                         "arguments": {"path": "does-not-exist.mp4"}}})
        send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
              "params": {"name": "when",
                         "arguments": {"path": str(media["flash"]),
                                       "text": "ERROR"}}})
        deadline = time.time() + 120
        while time.time() < deadline and not {2, 3, 4, 5} <= responses.keys():
            time.sleep(0.2)
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert {2, 3, 4, 5} <= responses.keys(), f"responses seen: {sorted(responses)}"
    tools = {t["name"] for t in responses[2]["result"]["tools"]}
    assert tools == {"probe", "timing", "diff", "scenes", "report", "audio",
                     "ocr", "find", "ask", "live", "speech", "when", "shot",
                     "strip", "clip", "ci", "trace", "record_android", "srt",
                     "rundiff", "load", "bugpack", "text", "redact",
                     "locate", "judge", "moments",
                     "contrast"}  # every CLI command, exactly

    call = responses[3]["result"]
    assert not call.get("isError"), call
    parsed = call.get("structuredContent") or json.loads(call["content"][0]["text"])
    if "result" in parsed:  # SDK wraps bare dict returns
        parsed = parsed["result"]
    assert parsed["video"]["width"] == 320

    bad = responses[4]["result"]
    assert bad.get("isError") is True
    assert "file not found" in bad["content"][0]["text"]

    hit = responses[5]["result"]
    assert not hit.get("isError"), hit
    parsed = hit.get("structuredContent") or json.loads(hit["content"][0]["text"])
    if "result" in parsed:
        parsed = parsed["result"]
    assert parsed["found"] is True and parsed["mode"] == "text"


@pytest.fixture(scope="module")
def mcp(media):
    """One running stdio server shared by the per-tool tests below.

    VIDQA_PRESENTMON is forced to a nonexistent path so the live tool's
    error contract is deterministic even on machines with a bundled exe.
    """
    env = dict(os.environ, VIDQA_PRESENTMON="vidqa-tests-no-such-presentmon.exe")
    proc = subprocess.Popen(
        [sys.executable, "-m", "vidqa.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env,
    )
    responses = {}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "id" in msg:
                responses[msg["id"]] = msg

    threading.Thread(target=reader, daemon=True).start()
    ids = itertools.count(1)

    def rpc(method, params=None, timeout=180):
        i = next(ids)
        msg = {"jsonrpc": "2.0", "id": i, "method": method}
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline and i not in responses:
            time.sleep(0.1)
        assert i in responses, f"no response to {method} (id {i})"
        return responses[i]

    def call(name, arguments):
        return rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "0"}})
    proc.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    yield SimpleNamespace(rpc=rpc, call=call)

    try:
        proc.stdin.close()
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def _unwrap(result):
    parsed = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    if "result" in parsed:  # SDK wraps bare dict returns
        parsed = parsed["result"]
    return parsed


def _rules(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"rules": [{"type": "no_blank_frames"}]}),
                    encoding="utf-8")
    return str(path)


def _tracezip(tmp_path):
    path = tmp_path / "trace.zip"
    events = [
        {"type": "context-options", "monotonicTime": 1000.0,
         "wallTime": 1722400000000},
        {"type": "before", "callId": "call@1", "startTime": 1500.0,
         "class": "Frame", "method": "goto",
         "params": {"url": "http://x", "timeout": 30000}},
        {"type": "after", "callId": "call@1", "endTime": 2200.0},
    ]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("trace.trace", "\n".join(json.dumps(e) for e in events))
    return str(path)


# probe and when get their round-trips in test_mcp_stdio_roundtrip above;
# every other tool with a deterministic happy path is here.
OK = {
    "timing": lambda m, t: {"path": str(m["clean"])},
    "diff": lambda m, t: {"candidate": str(m["same"]), "golden": str(m["golden"])},
    "scenes": lambda m, t: {"path": str(m["cut"])},
    "report": lambda m, t: {"path": str(m["clean"])},
    "audio": lambda m, t: {"path": str(m["av"])},
    "shot": lambda m, t: {"path": str(m["clean"]), "out": str(t / "shot.png"),
                          "at": 0.5},
    "moments": lambda m, t: {"path": str(m["cut"])},
    "contrast": lambda m, t: {"path": str(m["flash"]), "at": 1.5},
    "locate": lambda m, t: {"path": str(m["flash"]), "fail_text": "ERROR"},
    "text": lambda m, t: {"path": str(m["flash"]), "step": 1.0},
    "redact": lambda m, t: {"path": str(m["clean"]),
                            "out": str(t / "redacted.mp4"),
                            "regions": [[10, 10, 50, 50]]},
    "strip": lambda m, t: {"path": str(m["clean"]), "out": str(t / "strip.png")},
    "clip": lambda m, t: {"path": str(m["clean"]), "out": str(t / "clip.mp4"),
                          "start": 0.2, "end": 0.8},
    "load": lambda m, t: {"path": str(m["clean"])},
    "bugpack": lambda m, t: {"path": str(m["clean"]), "at": 0.5,
                             "out": str(t / "pack")},
    "srt": lambda m, t: {"path": str(m["cut"]), "out": str(t / "events.srt")},
    "rundiff": lambda m, t: {"a": str(m["clean"]), "b": str(m["clean"]),
                             "step": 1.0},
    "ci": lambda m, t: {"path": str(m["clean"]), "rules": _rules(t)},
    "trace": lambda m, t: {"path": _tracezip(t)},
    "ocr": lambda m, t: {"path": str(m["text"])},
    "find": lambda m, t: {"path": str(m["golden"]), "template": str(m["tpl"])},
}

# Tools whose happy path needs a model, device, or ETW session: their
# deterministic contract through MCP is the early-validation error.
ERR = {
    "judge": (lambda m, t: {"path": "no-such.mp4", "rubric": "no-such.md"},
              ("file not found",)),
    "ask": (lambda m, t: {"path": "no-such.mp4", "question": "ok?"},
            ("file not found",)),
    "speech": (lambda m, t: {"path": "no-such.mp4"}, ("file not found",)),
    "live": (lambda m, t: {"process": "no-such-process.exe", "seconds": 1},
             ("PresentMon exe not found",)),
    "record_android": (lambda m, t: {"cmd": "echo hi", "out": str(t / "rec.mp4"),
                                     "serial": "vidqa-no-such-device"},
                       ("adb not found", "no Android device ready")),
}


@pytest.mark.parametrize("name", sorted(OK))
def test_tool_roundtrip(mcp, media, tmp_path, name):
    result = mcp.call(name, OK[name](media, tmp_path))
    assert not result.get("isError"), result
    parsed = _unwrap(result)
    assert isinstance(parsed, dict) and parsed


@pytest.mark.parametrize("name", sorted(ERR))
def test_tool_error_contract(mcp, media, tmp_path, name):
    build, needles = ERR[name]
    result = mcp.call(name, build(media, tmp_path))
    assert result.get("isError") is True, result
    text = result["content"][0]["text"]
    assert any(n in text for n in needles), text


def test_mcp_roster_matches_cli_commands(mcp):
    tools = {t["name"] for t in mcp.rpc("tools/list")["result"]["tools"]}
    proc = subprocess.run([sys.executable, "-m", "vidqa.cli", "--help"],
                          capture_output=True, text=True)
    match = re.search(r"\{([a-z0-9_,-]+)\}", proc.stdout)
    assert match, proc.stdout
    cli = set(match.group(1).split(","))
    assert {t.replace("_", "-") for t in tools} == cli

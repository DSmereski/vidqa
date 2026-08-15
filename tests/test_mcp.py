"""MCP surface e2e: one real stdio server, every registered tool through it."""
import itertools
import json
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from test_ci import rules_file
from test_trace import make_trace
from vidqa.cli import subcommands
from vidqa.ffutil import ERR_FILE_NOT_FOUND
from vidqa.live import ERR_NO_PRESENTMON
from vidqa.record_android import ERR_NO_ADB, ERR_NO_DEVICE


@pytest.fixture(scope="module")
def mcp(media):
    """One running stdio server shared by every test in this module.

    VIDQA_PRESENTMON is forced to a nonexistent path so the live tool's
    error contract is deterministic even on machines with a bundled exe.
    Teardown asserts the server exits 0 with a silent stderr, so a native
    teardown crash or log noise fails the suite instead of hiding.
    """
    env = dict(os.environ, VIDQA_PRESENTMON="vidqa-tests-no-such-presentmon.exe")
    proc = subprocess.Popen(
        [sys.executable, "-m", "vidqa.mcp_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    responses = {}
    stderr_lines = []

    def read_stdout():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and "id" in msg:
                responses[msg["id"]] = msg

    threading.Thread(target=read_stdout, daemon=True).start()
    threading.Thread(target=lambda: stderr_lines.extend(proc.stderr),
                     daemon=True).start()
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
            assert proc.poll() is None, (
                f"server died (rc {proc.returncode}): "
                + "".join(stderr_lines)[-2000:])
            time.sleep(0.1)
        assert i in responses, f"no response to {method} (id {i})"
        resp = responses[i]
        assert "error" not in resp, resp["error"]
        return resp

    def call(name, arguments):
        return rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    init = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "0"}})
    assert "result" in init, init
    proc.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    yield SimpleNamespace(rpc=rpc, call=call)

    proc.stdin.close()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    assert proc.returncode == 0, f"server exited {proc.returncode}"
    assert not stderr_lines, "".join(stderr_lines)[-2000:]


def _payload(result):
    # bare `-> dict` tools: the SDK serializes the return value as the text
    # content, unwrapped, and leaves structuredContent unset
    return json.loads(result["content"][0]["text"])


def _trace_events():
    return [
        {"type": "context-options", "monotonicTime": 1000.0,
         "wallTime": 1722400000000},
        {"type": "before", "callId": "call@1", "startTime": 1500.0,
         "class": "Frame", "method": "goto",
         "params": {"url": "http://x", "timeout": 30000}},
        {"type": "after", "callId": "call@1", "endTime": 2200.0},
    ]


# (args, check) per tool with a deterministic happy path; the check must
# catch a functionally dead tool, not just a transport failure.
OK = {
    "timing": (lambda m, t: {"path": str(m["clean"])},
               lambda p, t: p["dup_frames"] == 0),
    "diff": (lambda m, t: {"candidate": str(m["same"]), "golden": str(m["golden"])},
             lambda p, t: p["pass"] is True),
    "scenes": (lambda m, t: {"path": str(m["cut"])},
               lambda p, t: p["scene_count"] == 2),
    "report": (lambda m, t: {"path": str(m["clean"])},
               lambda p, t: p["verdict"]["pass"] is True),
    "audio": (lambda m, t: {"path": str(m["av"])},
              lambda p, t: p["clipping_suspected"] is False),
    "shot": (lambda m, t: {"path": str(m["clean"]), "out": str(t / "shot.png"),
                           "at": 0.5},
             lambda p, t: (t / "shot.png").exists()),
    "moments": (lambda m, t: {"path": str(m["cut"])},
                lambda p, t: any(x["type"] == "cut" for x in p["moments"])),
    "contrast": (lambda m, t: {"path": str(m["flash"]), "at": 1.5},
                 lambda p, t: p["checked"] >= 1),
    "locate": (lambda m, t: {"path": str(m["flash"]), "fail_text": "ERROR"},
               lambda p, t: p["found"] is True and p["first_bad_s"] == 1.0),
    "text": (lambda m, t: {"path": str(m["flash"]), "step": 1.0},
             lambda p, t: any("ERROR" in x["text"].upper() for x in p["lines"])),
    "redact": (lambda m, t: {"path": str(m["clean"]),
                             "out": str(t / "redacted.mp4"),
                             "regions": [[10, 10, 50, 50]]},
               lambda p, t: (t / "redacted.mp4").exists()),
    "strip": (lambda m, t: {"path": str(m["clean"]), "out": str(t / "strip.png")},
              lambda p, t: (t / "strip.png").exists()),
    "clip": (lambda m, t: {"path": str(m["clean"]), "out": str(t / "clip.mp4"),
                           "start": 0.2, "end": 0.8},
             lambda p, t: (t / "clip.mp4").exists()),
    "load": (lambda m, t: {"path": str(m["clean"])},
             lambda p, t: p["first_content_s"] == 0.0),
    "bugpack": (lambda m, t: {"path": str(m["clean"]), "at": 0.5,
                              "out": str(t / "pack")},
                lambda p, t: "summary.md" in p["files"]),
    "srt": (lambda m, t: {"path": str(m["cut"]), "out": str(t / "events.srt")},
            lambda p, t: (t / "events.srt").exists()),
    "rundiff": (lambda m, t: {"a": str(m["clean"]), "b": str(m["clean"]),
                              "step": 1.0},
                lambda p, t: p["diverged"] is False),
    "ci": (lambda m, t: {"path": str(m["clean"]),
                         "rules": rules_file(t, {"type": "no_blank_frames"})},
           lambda p, t: p["pass"] is True),
    "trace": (lambda m, t: {"path": make_trace(t / "trace.zip", _trace_events())},
              lambda p, t: p["step_count"] == 1),
    "ocr": (lambda m, t: {"path": str(m["text"])},
            lambda p, t: p["block_count"] >= 1),
    "find": (lambda m, t: {"path": str(m["golden"]), "template": str(m["tpl"])},
             lambda p, t: p["found"] is True),
}

# Tools whose happy path needs a model, device, or ETW session: their
# deterministic contract through MCP is the early-validation error,
# matched on the stable prefixes the modules export.
ERR = {
    "judge": (lambda m, t: {"path": "no-such.mp4", "rubric": "no-such.md"},
              (ERR_FILE_NOT_FOUND,)),
    "ask": (lambda m, t: {"path": "no-such.mp4", "question": "ok?"},
            (ERR_FILE_NOT_FOUND,)),
    "speech": (lambda m, t: {"path": "no-such.mp4"}, (ERR_FILE_NOT_FOUND,)),
    "live": (lambda m, t: {"process": "no-such-process.exe", "seconds": 1},
             (ERR_NO_PRESENTMON,)),
    "record_android": (lambda m, t: {"cmd": "echo hi", "out": str(t / "rec.mp4"),
                                     "serial": "vidqa-no-such-device"},
                       (ERR_NO_ADB, ERR_NO_DEVICE)),
}


@pytest.mark.parametrize("name", sorted(OK))
def test_tool_roundtrip(mcp, media, tmp_path, name):
    build, check = OK[name]
    result = mcp.call(name, build(media, tmp_path))
    assert not result.get("isError"), result
    parsed = _payload(result)
    assert check(parsed, tmp_path), parsed


@pytest.mark.parametrize("name", sorted(ERR))
def test_tool_error_contract(mcp, media, tmp_path, name):
    build, needles = ERR[name]
    result = mcp.call(name, build(media, tmp_path))
    assert result.get("isError") is True, result
    text = result["content"][0]["text"]
    assert any(n in text for n in needles), text


def test_probe_roundtrip_deep(mcp, media):
    result = mcp.call("probe", {"path": str(media["clean"])})
    assert not result.get("isError"), result
    assert _payload(result)["video"]["width"] == 320


def test_missing_file_is_error(mcp):
    result = mcp.call("probe", {"path": "does-not-exist.mp4"})
    assert result.get("isError") is True
    assert ERR_FILE_NOT_FOUND in result["content"][0]["text"]


def test_when_roundtrip_deep(mcp, media):
    result = mcp.call("when", {"path": str(media["flash"]), "text": "ERROR"})
    assert not result.get("isError"), result
    parsed = _payload(result)
    assert parsed["found"] is True and parsed["mode"] == "text"


def test_mcp_roster_matches_cli_commands(mcp):
    tools = {t["name"] for t in mcp.rpc("tools/list")["result"]["tools"]}
    assert {t.replace("_", "-") for t in tools} == set(subcommands())


def test_mcp_exposes_cli_tuning_knobs(mcp):
    tools = {t["name"]: t for t in mcp.rpc("tools/list")["result"]["tools"]}
    knobs = {"scenes": {"threshold"}, "when": {"threshold"},
             "find": {"threshold"}, "diff": {"ssim_min", "cell_max", "mask_out"}}
    for name, want in knobs.items():
        props = set(tools[name]["inputSchema"]["properties"])
        assert want <= props, (name, sorted(props))


def test_knob_reaches_the_module(mcp, media):
    result = mcp.call("scenes", {"path": str(media["cut"]), "threshold": 95})
    parsed = _payload(result)
    assert parsed["scene_count"] == 1 and parsed["cuts"] == []

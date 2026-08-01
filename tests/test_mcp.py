import json
import subprocess
import sys
import threading
import time


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
                     "rundiff", "load", "bugpack"}  # every CLI command, exactly

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

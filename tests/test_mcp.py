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
        deadline = time.time() + 60
        while time.time() < deadline and not (2 in responses and 3 in responses):
            time.sleep(0.2)
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert 2 in responses and 3 in responses, f"responses seen: {sorted(responses)}"
    tools = {t["name"] for t in responses[2]["result"]["tools"]}
    assert {"probe", "timing", "diff", "scenes", "report",
            "audio", "ocr", "find", "ask"} <= tools

    call = responses[3]["result"]
    assert not call.get("isError"), call
    parsed = call.get("structuredContent") or json.loads(call["content"][0]["text"])
    if "result" in parsed:  # SDK wraps bare dict returns
        parsed = parsed["result"]
    assert parsed["video"]["width"] == 320

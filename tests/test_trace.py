import json
import subprocess
import sys
import zipfile

import pytest

from vidqa.trace import trace


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def make_trace(path, events):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("trace.trace", "\n".join(json.dumps(e) for e in events))
    return str(path)


@pytest.fixture()
def tracezip(tmp_path):
    # mirrors the real 1.6x event shape: class+method, no apiName
    return make_trace(tmp_path / "trace.zip", [
        {"type": "context-options", "monotonicTime": 1000.0, "wallTime": 1722400000000},
        {"type": "before", "callId": "call@1", "startTime": 1500.0, "class": "Frame",
         "method": "goto", "params": {"url": "http://x", "timeout": 30000}},
        {"type": "after", "callId": "call@1", "endTime": 2200.0},
        {"type": "before", "callId": "call@2", "startTime": 2500.0, "class": "Frame",
         "method": "click", "params": {"selector": "#buy", "timeout": 30000}},
        {"type": "after", "callId": "call@2", "endTime": 2600.0},
    ])


def test_steps_parsed_with_relative_times(tracezip):
    result = trace(tracezip)
    assert result["step_count"] == 2
    goto, click = result["steps"]
    assert goto["title"] == "frame.goto" and goto["url"] == "http://x"
    assert (goto["start_s"], goto["end_s"]) == (0.5, 1.2)
    assert click["title"] == "frame.click" and click["selector"] == "#buy"
    assert (click["start_s"], click["end_s"]) == (1.5, 1.6)


def test_at_step_extracts_completed_state_frame(tracezip, media, tmp_path):
    out = tmp_path / "step.png"
    result = trace(tracezip, video=str(media["flash"]), at_step="click", out=str(out))
    assert result["found"] is True and out.exists()
    assert result["shot"]["at_s"] == 1.6  # click end lands inside the text window
    from vidqa.ocr import ocr
    assert "ERROR" in ocr(str(out))["joined"].upper()


def test_unknown_step_exits_1(tracezip, media, tmp_path):
    proc = run_cli("trace", tracezip, "--video", str(media["flash"]),
                   "--at-step", "page.dblclick", "--out", str(tmp_path / "x.png"))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["found"] is False


def test_not_a_trace_exits_2(tmp_path, media):
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "hi")
    assert run_cli("trace", str(empty)).returncode == 2
    notzip = tmp_path / "notzip.zip"
    notzip.write_text("nope", encoding="utf-8")
    assert run_cli("trace", str(notzip)).returncode == 2

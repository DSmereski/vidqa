import json
import subprocess
import sys

from vidqa.when import when


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_text_interval_located(media):
    result = when(str(media["flash"]), text="ERROR")
    assert result["found"] is True
    assert result["mode"] == "text"
    iv = result["intervals"][0]
    assert abs(iv["start_s"] - 1.0) <= 0.5
    assert abs(iv["end_s"] - 2.0) <= 0.5
    assert result["first_s"] == iv["start_s"]


def test_text_absent_exits_1(media):
    proc = run_cli("when", str(media["flash"]), "NO SUCH TEXT")
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["found"] is False and out["intervals"] == []


def test_template_interval_located(media):
    result = when(str(media["flash"]), template=str(media["flash_tpl"]))
    assert result["found"] is True
    assert result["mode"] == "template"
    iv = result["intervals"][0]
    assert iv["start_s"] <= 1.5 <= iv["end_s"]


def test_needs_exactly_one_query(media):
    proc = run_cli("when", str(media["flash"]))
    assert proc.returncode == 2


def test_deterministic(media):
    a = run_cli("when", str(media["flash"]), "ERROR")
    b = run_cli("when", str(media["flash"]), "ERROR")
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout

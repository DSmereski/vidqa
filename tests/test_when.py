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


def test_sampling_reads_the_frame_at_each_instant(media):
    """Sample i is the frame ON SCREEN at instant i*step (fps round=up).
    The filter's default rounding emits the frame from ~(i+0.5)*step,
    which made every reported timestamp run half a step early and missed
    this [1,2] window entirely at step 1.5. A window that fits wholly
    between instants is still missable — pick a step no larger than the
    shortest state you need to catch."""
    found = when(str(media["flash"]), text="ERROR", step=1.5)
    assert found["found"] is True  # instant 1.5 lies inside the [1,2] window
    assert found["intervals"][0]["start_s"] == 1.5
    missed = when(str(media["flash"]), text="ERROR", step=3.0)
    assert missed["found"] is False  # no sample instant lands inside [1,2]

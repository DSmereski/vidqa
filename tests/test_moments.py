import json
import subprocess
import sys

from vidqa.ffutil import jdump
from vidqa.moments import moments


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_freeze_indexed(media):
    result = moments(str(media["freeze"]))
    assert result["counts"].get("freeze", 0) >= 1
    kinds = {m["type"] for m in result["moments"]}
    assert "freeze" in kinds


def test_cut_indexed(media):
    result = moments(str(media["cut"]))
    cuts = [m for m in result["moments"] if m["type"] == "cut"]
    assert cuts and abs(cuts[0]["at_s"] - 1.0) <= 0.2


def test_blank_span_on_uniform_video(media):
    result = moments(str(media["red"]))
    blanks = [m for m in result["moments"] if m["type"] == "blank"]
    assert len(blanks) == 1
    assert blanks[0]["at_s"] == 0.0 and blanks[0]["end_s"] >= 1.5


def test_text_first_last_marked(media):
    result = moments(str(media["flash"]), text="ERROR")
    assert result["query_found"] is True
    firsts = [m for m in result["moments"] if m["type"] == "text_first"]
    assert firsts and abs(firsts[0]["at_s"] - 1.0) <= 0.5


def test_text_absent_still_exits_0(media):
    proc = run_cli("moments", str(media["flash"]), "--text", "ZEBRA")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["query_found"] is False


def test_timeline_sorted_and_counted(media):
    result = moments(str(media["cut"]))
    ats = [m["at_s"] for m in result["moments"]]
    assert ats == sorted(ats)
    assert sum(result["counts"].values()) == result["moment_count"]


def test_deterministic(media):
    assert jdump(moments(str(media["freeze"]))) == \
        jdump(moments(str(media["freeze"])))

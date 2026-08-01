import json
import subprocess
import sys

from vidqa.bugpack import bugpack


def test_evidence_folder_contents(media, tmp_path):
    out = tmp_path / "pack"
    result = bugpack(str(media["freeze"]), 1.0, str(out), title="frozen build")
    names = sorted(p.name for p in out.iterdir())
    assert names == ["clip.mp4", "events.srt", "frame.png", "report.json", "summary.md"]
    assert result["files"] == names
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("# frozen build")
    assert "freeze@" in summary
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["verdict"]["pass"] is False
    from vidqa.probe import probe
    src = probe(str(media["freeze"]))["duration_s"]
    expected = min(src, 1.0 + 3.0)  # at=1.0, span clamped to [0, src]
    assert abs(probe(str(out / "clip.mp4"))["duration_s"] - expected) <= 0.3


def test_cli_always_exits_0(media, tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "vidqa.cli", "bugpack", str(media["freeze"]),
         "--at", "1.0", "--out", str(tmp_path / "p2")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["issues"]  # failing verdict rides in the JSON

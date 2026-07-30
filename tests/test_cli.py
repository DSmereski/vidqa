import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def test_missing_file_exits_2(media):
    proc = run_cli("timing", "does-not-exist.mp4")
    assert proc.returncode == 2
    assert "file not found" in proc.stderr


def test_diff_gate_exit_codes(media):
    ok = run_cli("diff", str(media["same"]), "--golden", str(media["golden"]))
    assert ok.returncode == 0
    bad = run_cli("diff", str(media["corrupt"]), "--golden", str(media["golden"]))
    assert bad.returncode == 1


def test_output_is_deterministic_and_compact(media):
    first = run_cli("timing", str(media["freeze"]))
    second = run_cli("timing", str(media["freeze"]))
    third = run_cli("timing", str(media["freeze"]))
    assert first.returncode == 0
    assert first.stdout == second.stdout == third.stdout
    assert len(first.stdout.encode()) <= 4096
    parsed = json.loads(first.stdout)
    assert parsed["dup_frames"] == 12

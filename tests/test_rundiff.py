import json
import subprocess
import sys

import pytest

from vidqa.rundiff import rundiff


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    """Two runs identical until t=1.5, then run b grows a big white box."""
    root = tmp_path_factory.mktemp("rundiff")

    def ff(*args):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        *args], check=True)

    a = root / "run_a.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=duration=3:size=320x240:rate=25",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(a))
    b = root / "run_b.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=duration=3:size=320x240:rate=25",
       "-vf", "drawbox=x=40:y=40:w=240:h=160:color=white:t=fill:enable='gte(t,1.5)'",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(b))
    return {"a": a, "b": b}


def test_same_file_never_diverges(media):
    result = rundiff(str(media["clean"]), str(media["clean"]))
    assert result["diverged"] is False
    assert result["first_divergence_s"] is None
    assert result["mean_distance"] == 0.0


def test_divergence_located_and_gated(pair, tmp_path):
    shots = tmp_path / "shots"
    result = rundiff(str(pair["a"]), str(pair["b"]), shots=str(shots))
    assert result["diverged"] is True
    assert 1.0 <= result["first_divergence_s"] <= 2.0
    assert (shots / "diverge_a.png").exists() and (shots / "diverge_b.png").exists()
    proc = run_cli("rundiff", str(pair["a"]), str(pair["b"]))
    assert proc.returncode == 1


def test_duration_mismatch_is_visible(media, pair):
    result = rundiff(str(media["clean"]), str(pair["a"]))  # 2 s vs 3 s
    assert result["duration_b_s"] - result["duration_a_s"] >= 0.5


def test_deterministic(pair):
    first = run_cli("rundiff", str(pair["a"]), str(pair["b"]))
    second = run_cli("rundiff", str(pair["a"]), str(pair["b"]))
    assert first.stdout == second.stdout
    out = json.loads(first.stdout)
    assert out["sampled"] == 6  # 3 s at 0.5 s step

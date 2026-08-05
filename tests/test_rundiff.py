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


@pytest.fixture(scope="module")
def hue_pair(tmp_path_factory):
    """Same dark page, but the status panel is green in a / red in b at a
    matched gray value (37 vs 33) — invisible to grayscale pHash/SSIM."""
    root = tmp_path_factory.mktemp("hue")

    def panel(color, out):
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=c=0x12141a:duration=2:size=320x240:rate=25",
             "-vf", f"drawbox=x=80:y=60:w=160:h=120:color={color}@1:t=fill",
             "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(out)],
            check=True)
        return out

    return {"green": panel("0x12301e", root / "green.mp4"),
            "red": panel("0x4a1010", root / "red.mp4")}


def test_same_file_never_diverges(media):
    result = rundiff(str(media["clean"]), str(media["clean"]))
    assert result["diverged"] is False
    assert result["first_divergence_s"] is None
    assert result["mean_distance"] == 0.0


def test_hue_swap_caught_by_color_not_phash(hue_pair):
    result = rundiff(str(hue_pair["green"]), str(hue_pair["red"]))
    assert result["diverged"] is True
    first = result["divergences"][0]
    assert first["color_gap"] > result["color_threshold"]
    assert first["distance"] <= result["threshold"]  # pHash alone misses it


def test_hue_swap_caught_in_step_mode(hue_pair, tmp_path):
    ta = step_trace(tmp_path / "a.zip", [("goto", 1.0)])
    tb = step_trace(tmp_path / "b.zip", [("goto", 1.0)])
    result = rundiff(str(hue_pair["green"]), str(hue_pair["red"]),
                     trace_a=ta, trace_b=tb)
    assert result["diverged"] is True
    assert result["steps"][0]["color_gap"] > result["color_threshold"]


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


def test_ignore_suppresses_known_dynamic_region(pair):
    result = rundiff(str(pair["a"]), str(pair["b"]),
                     ignore=[[40, 40, 240, 160]])  # exactly the injected box
    assert result["diverged"] is False
    assert result["ignored"] == [[40, 40, 240, 160]]
    proc = run_cli("rundiff", str(pair["a"]), str(pair["b"]),
                   "--ignore", "40,40,240,160")
    assert proc.returncode == 0


def step_trace(path, methods_ends):
    import zipfile
    events = []
    for i, (method, end_s) in enumerate(methods_ends, 1):
        events.append({"type": "before", "callId": f"call@{i}",
                       "startTime": 1000.0 + i, "class": "Frame",
                       "method": method, "params": {}})
        events.append({"type": "after", "callId": f"call@{i}",
                       "endTime": 1000.0 + 1 + end_s * 1000.0})
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("trace.trace", "\n".join(json.dumps(e) for e in events))
    return str(path)


def test_step_aligned_divergence(pair, tmp_path):
    ta = step_trace(tmp_path / "a.zip", [("goto", 1.0), ("click", 2.0)])
    tb = step_trace(tmp_path / "b.zip", [("goto", 1.0), ("click", 2.0)])
    shots = tmp_path / "shots"
    result = rundiff(str(pair["a"]), str(pair["b"]),
                     trace_a=ta, trace_b=tb, shots=str(shots))
    assert result["mode"] == "steps"
    assert [s["diverged"] for s in result["steps"]] == [False, True]
    assert result["first_divergent_step"] == "frame.click"
    assert result["diverged"] is True
    assert (shots / "diverge_a.png").exists()


def test_step_mode_same_video_matches(pair, tmp_path):
    ta = step_trace(tmp_path / "a.zip", [("goto", 1.0), ("click", 2.0)])
    tb = step_trace(tmp_path / "b.zip", [("goto", 1.0), ("click", 2.0)])
    result = rundiff(str(pair["a"]), str(pair["a"]), trace_a=ta, trace_b=tb)
    assert result["diverged"] is False
    assert result["first_divergent_step"] is None


def test_step_title_mismatch_is_divergence(pair, tmp_path):
    ta = step_trace(tmp_path / "a.zip", [("goto", 1.0), ("click", 2.0)])
    tb = step_trace(tmp_path / "b.zip", [("goto", 1.0), ("dblclick", 2.0)])
    result = rundiff(str(pair["a"]), str(pair["b"]), trace_a=ta, trace_b=tb)
    assert result["diverged"] is True
    assert result["step_mismatch"] == {"index": 1, "a": "frame.click",
                                       "b": "frame.dblclick"}

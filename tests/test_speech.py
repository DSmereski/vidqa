import json
import subprocess
import sys

import pytest

pytest.importorskip("faster_whisper")

PHRASE = "the quick brown fox jumps over the lazy dog"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def spoken(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("fixture is synthesized with Windows SAPI text-to-speech")
    root = tmp_path_factory.mktemp("speech")
    wav = root / "tts.wav"
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('{PHRASE}'); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    clip = root / "spoken.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=black:size=320x240:rate=25",
         "-i", str(wav), "-shortest",
         "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p",
         "-c:a", "aac", str(clip)],
        check=True,
    )
    return clip


def test_transcript_recovers_spoken_words(spoken):
    proc = run_cli("speech", str(spoken), "--model", "tiny")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    words = set(out["text"].lower().replace(".", "").replace(",", "").split())
    assert len(words & set(PHRASE.split())) >= 6
    assert out["language"] == "en"
    assert out["segment_count"] >= 1
    assert out["truncated"] is False
    assert "segments" not in out  # compact by default; --full opts in


def test_expect_substring_gate(spoken):
    ok = run_cli("speech", str(spoken), "--model", "tiny", "--expect", "brown fox")
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["expect_found"] is True
    bad = run_cli("speech", str(spoken), "--model", "tiny", "--expect", "purple zebra")
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["expect_found"] is False


def test_find_returns_timestamped_matches(spoken):
    ok = run_cli("speech", str(spoken), "--model", "tiny", "--find", "brown fox")
    assert ok.returncode == 0, ok.stderr
    out = json.loads(ok.stdout)
    assert out["find_found"] is True
    assert out["find_matches"] and {"start", "end", "text"} <= set(out["find_matches"][0])
    bad = run_cli("speech", str(spoken), "--model", "tiny", "--find", "purple zebra")
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["find_matches"] == []


def test_full_includes_segments(spoken):
    proc = run_cli("speech", str(spoken), "--model", "tiny", "--full")
    assert proc.returncode == 0, proc.stderr
    segs = json.loads(proc.stdout)["segments"]
    assert segs and {"start", "end", "text"} <= set(segs[0])


def test_missing_dependency_is_clean_error(spoken, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    from vidqa.cli import main
    code = main(["speech", str(spoken)])
    assert code == 2


def test_no_audio_stream_is_clean_error(media):
    proc = run_cli("speech", str(media["clean"]), "--model", "tiny")
    assert proc.returncode == 2
    assert "audio" in proc.stderr.lower()

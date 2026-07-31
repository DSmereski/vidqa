import re
import subprocess
import sys

from vidqa.srt import srt

ARROW = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vidqa.cli", *args],
        capture_output=True, text=True,
    )


def parse(text):
    cues = []
    for block in [b for b in text.split("\n\n") if b.strip()]:
        idx, arrow, label = block.strip().split("\n")
        assert ARROW.match(arrow), arrow
        start = arrow.split(" --> ")[0]
        h, m, rest = start.split(":")
        s, ms = rest.split(",")
        t = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        cues.append((int(idx), t, label))
    return cues


def test_freeze_becomes_a_cue(media, tmp_path):
    out = tmp_path / "ev.srt"
    result = srt(str(media["freeze"]), str(out))
    assert result["counts"]["freeze"] >= 1
    cues = parse(out.read_text(encoding="utf-8"))
    assert [c[0] for c in cues] == list(range(1, len(cues) + 1))
    freeze = next(c for c in cues if c[2].startswith("freeze"))
    assert abs(freeze[1] - 1.0) <= 0.2


def test_cut_and_silence_cues(media, tmp_path):
    cut_srt = tmp_path / "cut.srt"
    srt(str(media["cut"]), str(cut_srt))
    cut = next(c for c in parse(cut_srt.read_text(encoding="utf-8"))
               if c[2] == "scene cut")
    assert abs(cut[1] - 1.0) <= 0.2

    sil_srt = tmp_path / "sil.srt"
    result = srt(str(media["end_silence"]), str(sil_srt))
    assert result["counts"].get("silence", 0) >= 1


def test_srt_is_player_parseable(media, tmp_path):
    out = tmp_path / "ev.srt"
    srt(str(media["freeze"]), str(out))
    probe = subprocess.run(["ffprobe", "-v", "error", str(out)],
                           capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


def test_deterministic_and_exit_0(media, tmp_path):
    out = tmp_path / "ev.srt"
    first = run_cli("srt", str(media["freeze"]), "--out", str(out))
    first_bytes = out.read_bytes()
    second = run_cli("srt", str(media["freeze"]), "--out", str(out))
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert out.read_bytes() == first_bytes


def test_no_audio_video_still_works(media, tmp_path):
    out = tmp_path / "ev.srt"
    result = srt(str(media["clean"]), str(out))  # video-only fixture
    assert "silence" not in result["counts"]

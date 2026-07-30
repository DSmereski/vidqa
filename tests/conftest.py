"""Synthetic fixture videos, generated once per session with ffmpeg.

Everything is encoded libx264 -qp 0 so seeded artifacts (identical frames,
corrupt regions) survive encoding exactly and the asserts can be exact.
"""
import subprocess

import pytest

SIZE = "320x240"
FPS = 25


def ff(*args):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True
    )


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    root = tmp_path_factory.mktemp("media")

    clean = root / "clean.mp4"
    ff("-f", "lavfi", "-i", f"testsrc2=duration=2:size={SIZE}:rate={FPS}",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(clean))

    # 13 identical frames (12 dups, 0.52 s) injected at t=1.0, then re-timed CFR
    freeze = root / "freeze.mp4"
    graph = (
        "[0:v]split=3[a][m][b];"
        "[a]trim=end_frame=25,setpts=PTS-STARTPTS[va];"
        "[m]trim=start_frame=25:end_frame=26,loop=loop=12:size=1:start=0,"
        f"setpts=N/({FPS}*TB)[vm];"
        "[b]trim=start_frame=26,setpts=PTS-STARTPTS[vb];"
        f"[va][vm][vb]concat=n=3:v=1:a=0,setpts=N/({FPS}*TB)[out]"
    )
    ff("-f", "lavfi", "-i", f"testsrc2=duration=2:size={SIZE}:rate={FPS}",
       "-filter_complex", graph, "-map", "[out]",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(freeze))

    # drop frames 30-35 keeping timestamps -> one 280 ms pts gap at ~1.16 s
    gap = root / "gap.mp4"
    ff("-i", str(clean), "-vf", "select='not(between(n,30,35))'",
       "-fps_mode", "passthrough",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(gap))

    # hard cut: 1 s of red, then 1 s of smpte bars
    cut = root / "cut.mp4"
    ff("-f", "lavfi", "-i", f"color=red:duration=1:size={SIZE}:rate={FPS}",
       "-f", "lavfi", "-i", f"smptebars=duration=1:size={SIZE}:rate={FPS}",
       "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[out]", "-map", "[out]",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(cut))

    golden = root / "golden.png"
    ff("-ss", "0.5", "-i", str(clean), "-frames:v", "1", str(golden))
    same = root / "same.png"
    ff("-ss", "0.5", "-i", str(clean), "-frames:v", "1", str(same))
    corrupt = root / "corrupt.png"
    ff("-ss", "0.5", "-i", str(clean), "-frames:v", "1",
       "-vf", "drawbox=x=200:y=150:w=80:h=60:color=magenta:t=fill", str(corrupt))
    other = root / "other.png"
    ff("-f", "lavfi", "-i", f"smptebars=duration=0.1:size={SIZE}:rate={FPS}",
       "-frames:v", "1", str(other))
    small = root / "small.png"
    ff("-i", str(golden), "-vf", "scale=160:120", str(small))

    return {
        "clean": clean, "freeze": freeze, "gap": gap, "cut": cut,
        "golden": golden, "same": same, "corrupt": corrupt, "other": other,
        "small": small,
    }

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
def panel():
    """Builder for luma-matched hue-swap panels (green vs red at equal gray):
    dark page with one filled box. '.png' out = single frame, else 2 s clip."""
    def make(color, out):
        args = ["-f", "lavfi", "-i",
                f"color=c=0x12141a:duration=2:size={SIZE}:rate={FPS}",
                "-vf", f"drawbox=x=80:y=60:w=160:h=120:color={color}@1:t=fill"]
        if str(out).endswith(".png"):
            args += ["-frames:v", "1"]
        else:
            args += ["-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p"]
        ff(*args, str(out))
        return out
    return make


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

    # audio: 1 s tone, 2 s silence, 1 s tone
    silence_wav = root / "silence.wav"
    norm = "aformat=sample_fmts=s16:sample_rates=44100:channel_layouts=mono"
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=1",
       "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=2",
       "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
       "-filter_complex",
       f"[0:a]{norm}[a0];[1:a]{norm}[a1];[2:a]{norm}[a2];"
       "[a0][a1][a2]concat=n=3:v=0:a=1[out]",
       "-map", "[out]", str(silence_wav))

    # sine generates at 1/8 amplitude, so x20 drives it well past full scale
    clipped_wav = root / "clipped.wav"
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=1",
       "-af", "volume=20", str(clipped_wav))

    av = root / "av.mp4"
    ff("-f", "lavfi", "-i", f"testsrc2=duration=2:size={SIZE}:rate={FPS}",
       "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-shortest", str(av))

    text_png = root / "text.png"
    drawtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                "text='SCORE 12345 GAME OVER':fontsize=48:fontcolor=white:x=40:y=150")
    ff("-f", "lavfi", "-i", "color=black:size=640x360:rate=1:duration=1",
       "-frames:v", "1", "-vf", drawtext, str(text_png))

    tpl = root / "tpl.png"
    ff("-i", str(golden), "-vf", "crop=64:48:100:80", str(tpl))

    red = root / "red.mp4"
    ff("-f", "lavfi", "-i", f"color=red:duration=2:size={SIZE}:rate={FPS}",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(red))

    # audio dies at 0.7 s and never returns (ffmpeg 8 still closes the
    # silence at EOF, so this yields a terminated 1.3 s silence)
    end_silence = root / "endsilence.mkv"
    ff("-f", "lavfi", "-i", f"testsrc2=duration=2:size={SIZE}:rate={FPS}",
       "-f", "lavfi", "-i", "sine=frequency=440:duration=0.7",
       "-af", "apad", "-t", "2",
       "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p",
       "-c:a", "pcm_s16le", str(end_silence))

    # 'ERROR 500' on a black box, visible only t=1..2 of a 3 s clip
    flash = root / "flash.mp4"
    flashtext = ("drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
                 "text='ERROR 500':fontsize=40:fontcolor=white:"
                 "box=1:boxcolor=black:boxborderw=12:x=40:y=100:"
                 "enable='between(t,1,2)'")
    ff("-f", "lavfi", "-i", f"testsrc2=duration=3:size={SIZE}:rate={FPS}",
       "-vf", flashtext, "-c:v", "libx264", "-qp", "0",
       "-pix_fmt", "yuv420p", str(flash))
    flash_tpl = root / "flash_tpl.png"
    ff("-ss", "1.5", "-i", str(flash), "-frames:v", "1",
       "-vf", "crop=240:64:28:88", str(flash_tpl))

    return {
        "clean": clean, "freeze": freeze, "gap": gap, "cut": cut,
        "golden": golden, "same": same, "corrupt": corrupt, "other": other,
        "small": small, "silence_wav": silence_wav, "clipped_wav": clipped_wav,
        "av": av, "text": text_png, "tpl": tpl, "red": red,
        "end_silence": end_silence, "flash": flash, "flash_tpl": flash_tpl,
    }

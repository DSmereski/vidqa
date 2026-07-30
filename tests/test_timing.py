from vidqa.timing import timing


def test_clean_video_is_quiet(media):
    result = timing(str(media["clean"]))
    assert result["frame_count"] == 50
    assert result["na_frames"] == 0
    assert result["dup_frames"] == 0
    assert result["freeze_count"] == 0
    assert result["freezes"] == []
    assert result["stutter"]["event_count"] == 0
    assert 24.0 <= result["fps_effective"] <= 26.0


def test_freeze_detected_within_one_frame(media):
    result = timing(str(media["freeze"]))
    assert result["frame_count"] == 62
    assert result["dup_frames"] == 12
    assert result["freeze_count"] == 1
    freeze = result["freezes"][0]
    # injected at exactly t=1.0; criteria: found within +/-1 frame (40 ms)
    assert abs(freeze["start_s"] - 1.0) <= 0.06
    assert 0.4 <= freeze["duration_s"] <= 0.6


def test_pts_gap_flagged_as_stutter(media):
    result = timing(str(media["gap"]))
    assert result["dup_frames"] == 0
    assert result["stutter"]["event_count"] == 1
    event = result["stutter"]["events"][0]
    # 6 dropped frames + the kept one = 7 x 40 ms = 280 ms delta at ~1.16 s
    assert abs(event["delta_ms"] - 280.0) <= 5.0
    assert 1.0 <= event["t_s"] <= 1.3

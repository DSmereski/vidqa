from vidqa.scenes import scenes


def test_hard_cut_found(media):
    result = scenes(str(media["cut"]))
    assert result["scene_count"] == 2
    assert len(result["cuts"]) == 1
    assert abs(result["cuts"][0] - 1.0) <= 0.1


def test_clean_video_single_scene(media):
    result = scenes(str(media["clean"]))
    assert result["scene_count"] == 1
    assert result["cuts"] == []


def test_threshold_knob_routes(media):
    # raised far enough, even the hard red->bars cut stops counting
    result = scenes(str(media["cut"]), threshold=95)
    assert result["scene_count"] == 1
    assert result["cuts"] == []

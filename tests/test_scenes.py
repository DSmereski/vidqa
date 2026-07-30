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

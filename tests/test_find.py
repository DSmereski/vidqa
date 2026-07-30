from vidqa.find import find


def test_template_located_within_2px(media):
    result = find(str(media["golden"]), str(media["tpl"]))
    assert result["found"] is True
    assert abs(result["x"] - 100) <= 2
    assert abs(result["y"] - 80) <= 2


def test_template_absent(media):
    result = find(str(media["other"]), str(media["tpl"]))
    assert result["found"] is False

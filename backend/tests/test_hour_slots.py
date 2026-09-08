from domain.hour_slots import format_hour_label


def test_format_hour_label_before_18_slot() -> None:
    assert format_hour_label("~18") == "~18"


def test_format_hour_label_from_hour_slots() -> None:
    assert format_hour_label("18") == "18~"
    assert format_hour_label("19") == "19~"
    assert format_hour_label("23") == "23~"
    assert format_hour_label("00") == "00~"
    assert format_hour_label("06") == "06~"

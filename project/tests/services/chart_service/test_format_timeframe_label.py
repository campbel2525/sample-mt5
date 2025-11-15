from services.chart_service import format_timeframe_label


def test_format_timeframe_label_minutes() -> None:
    assert format_timeframe_label("M1") == "1分足"
    assert format_timeframe_label("M5") == "5分足"
    assert format_timeframe_label("M15") == "15分足"


def test_format_timeframe_label_hours() -> None:
    assert format_timeframe_label("H1") == "1時間足"
    assert format_timeframe_label("H4") == "4時間足"


def test_format_timeframe_label_day_and_week() -> None:
    assert format_timeframe_label("D1") == "日足"
    assert format_timeframe_label("W1") == "週足"


def test_format_timeframe_label_months() -> None:
    assert format_timeframe_label("MN1") == "1ヶ月足"
    assert format_timeframe_label("MN3") == "3ヶ月足"


def test_format_timeframe_label_fallback_other() -> None:
    # 想定外のコードはそのまま「◯足」として扱う
    assert format_timeframe_label("X10") == "X10足"
    assert format_timeframe_label("M") == "M足"
    assert format_timeframe_label("MN") == "MN足"
    assert format_timeframe_label("D2") == "D2足"

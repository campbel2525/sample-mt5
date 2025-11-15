from services.chart_service import is_death_cross


def test_is_death_cross_basic_true() -> None:
    # 直前は短期が長期以上、最新で短期が長期を下抜け
    assert is_death_cross(prev_short=12, prev_long=10, latest_short=9, latest_long=10)


def test_is_death_cross_equal_then_cross() -> None:
    # 直前はちょうど同値、最新で下抜け
    assert is_death_cross(prev_short=10, prev_long=10, latest_short=9, latest_long=10)


def test_is_death_cross_no_cross_latest_not_below() -> None:
    # 最新で短期が長期以上のまま
    assert not is_death_cross(
        prev_short=11,
        prev_long=10,
        latest_short=10,
        latest_long=10,
    )


def test_is_death_cross_no_cross_prev_below() -> None:
    # 直前からすでに短期が長期より下
    assert not is_death_cross(
        prev_short=9,
        prev_long=10,
        latest_short=8,
        latest_long=9,
    )

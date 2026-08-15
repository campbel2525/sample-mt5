from services.chart_service import is_golden_cross_by_ma


def test_is_golden_cross_by_ma_basic_true() -> None:
    # 直前は短期が長期以下、最新で短期が長期を上抜け
    assert is_golden_cross_by_ma(prev_short=10, prev_long=12, latest_short=13, latest_long=12)


def test_is_golden_cross_by_ma_equal_then_cross() -> None:
    # 直前はちょうど同値、最新で上抜け
    assert is_golden_cross_by_ma(prev_short=10, prev_long=10, latest_short=11, latest_long=10)


def test_is_golden_cross_by_ma_no_cross_latest_not_above() -> None:
    # 最新で短期が長期以下のまま
    assert not is_golden_cross_by_ma(
        prev_short=9,
        prev_long=10,
        latest_short=10,
        latest_long=10,
    )


def test_is_golden_cross_by_ma_no_cross_prev_above() -> None:
    # 直前からすでに短期が長期より上
    assert not is_golden_cross_by_ma(
        prev_short=11,
        prev_long=10,
        latest_short=12,
        latest_long=11,
    )

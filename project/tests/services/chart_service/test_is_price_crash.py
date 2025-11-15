from services.chart_service import is_price_crash


def test_is_price_crash_true_when_drop_exceeds_threshold() -> None:
    # 終値が十分に下落しているケース
    assert is_price_crash(prev_close=100.0, latest_close=90.0, min_drop=10.0)
    assert is_price_crash(prev_close=100.0, latest_close=89.0, min_drop=10.0)


def test_is_price_crash_false_when_drop_is_small() -> None:
    # 下落幅が閾値未満
    assert not is_price_crash(prev_close=100.0, latest_close=91.0, min_drop=10.0)


def test_is_price_crash_false_when_price_rose() -> None:
    # 価格が上昇している場合は常に False
    assert not is_price_crash(prev_close=100.0, latest_close=110.0, min_drop=5.0)


def test_is_price_crash_min_drop_non_positive() -> None:
    # min_drop が 0 以下の場合は常に False
    assert not is_price_crash(prev_close=100.0, latest_close=80.0, min_drop=0.0)
    assert not is_price_crash(prev_close=100.0, latest_close=80.0, min_drop=-5.0)

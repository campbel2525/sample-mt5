from services.chart_service import is_price_surge


def test_is_price_surge_true_when_rise_exceeds_threshold() -> None:
    # 終値が十分に上昇しているケース
    assert is_price_surge(prev_close=100.0, latest_close=110.0, min_rise=10.0)
    assert is_price_surge(prev_close=100.0, latest_close=111.0, min_rise=10.0)


def test_is_price_surge_false_when_rise_is_small() -> None:
    # 上昇幅が閾値未満
    assert not is_price_surge(prev_close=100.0, latest_close=109.0, min_rise=10.0)


def test_is_price_surge_false_when_price_dropped() -> None:
    # 価格が下落している場合は常に False
    assert not is_price_surge(prev_close=100.0, latest_close=90.0, min_rise=5.0)


def test_is_price_surge_min_rise_non_positive() -> None:
    # min_rise が 0 以下の場合は常に False
    assert not is_price_surge(prev_close=100.0, latest_close=120.0, min_rise=0.0)
    assert not is_price_surge(prev_close=100.0, latest_close=120.0, min_rise=-5.0)

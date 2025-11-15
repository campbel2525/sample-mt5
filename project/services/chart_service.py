from __future__ import annotations

from datetime import datetime
from typing import Tuple

Row = Tuple[datetime, float, float, float, float]


def format_timeframe_label(tf: str) -> str:
    """時間足コードを日本語ラベルへ変換する

    Args:
        tf: MT5 の時間足文字列（例: "M5", "H1"）
    """
    if tf.startswith("M") and tf[1:].isdigit():
        return f"{tf[1:]}分足"
    if tf.startswith("H") and tf[1:].isdigit():
        return f"{tf[1:]}時間足"
    if tf == "D1":
        return "日足"
    if tf == "W1":
        return "週足"
    if tf.startswith("MN") and tf[2:].isdigit():
        return f"{tf[2:]}ヶ月足"
    return f"{tf}足"


def is_golden_cross(
    prev_short: float,
    prev_long: float,
    latest_short: float,
    latest_long: float,
) -> bool:
    """ゴールデンクロス判定

    Args:
        prev_short: 直前バー短期移動平均
        prev_long: 直前バー長期移動平均
        latest_short: 最新バー短期移動平均
        latest_long: 最新バー長期移動平均
    """
    return prev_short <= prev_long and latest_short > latest_long


def is_death_cross(
    prev_short: float,
    prev_long: float,
    latest_short: float,
    latest_long: float,
) -> bool:
    """デッドクロス判定

    Args:
        prev_short: 直前バー短期移動平均
        prev_long: 直前バー長期移動平均
        latest_short: 最新バー短期移動平均
        latest_long: 最新バー長期移動平均
    """
    return prev_short >= prev_long and latest_short < latest_long


def is_price_crash(
    prev_close: float,
    latest_close: float,
    min_drop: float,
) -> bool:
    """指定値幅以上の下落になっているかを判定する

    Args:
        prev_close: 直前バーの終値
        latest_close: 最新バーの終値
        min_drop: 暴落とみなす最小下落幅
    """
    if min_drop <= 0:
        return False
    return (prev_close - latest_close) >= min_drop


def is_price_surge(
    prev_close: float,
    latest_close: float,
    min_rise: float,
) -> bool:
    """指定値幅以上の上昇になっているかを判定する

    Args:
        prev_close: 直前バーの終値
        latest_close: 最新バーの終値
        min_rise: 暴騰とみなす最小上昇幅
    """
    if min_rise <= 0:
        return False
    return (latest_close - prev_close) >= min_rise

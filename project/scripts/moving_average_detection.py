"""
移動平均線を検知してslackへ通知を出す
銘柄や足など個別に対応可能

- ゴールデンクロス
- デッドクロス
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from config.custom_logger import setup_logger
from config.settings import Settings
from services.chart_service import (
    format_timeframe_label,
    is_death_cross,
    is_golden_cross,
    is_price_crash,
    is_price_surge,
)
from services.mt5_service import get_market_data
from services.slack_service import notify_slack

settings = Settings()
logger = setup_logger(__name__, level=settings.log_level, fmt=settings.log_format)

# 設定
POLL_INTERVAL_SEC: float = 60.0
DEBUG_MODE: bool = settings.debug_mode
GET_CHART_COUNT: int = 2  # 取得するバー本数（末尾が最新）
MOVING_AVERAGE_METHOD: str = "SMA"  # 移動平均の算出方法
MOVING_AVERAGE_SHORT: int = 5  # 短期移動平均の期間
MOVING_AVERAGE_MIDDLE: int = 20  # 中期移動平均の期間
MOVING_AVERAGE_LONG: int = 60  # 長期移動平均の期間
RSI_PERIOD: int = 14  # RSI計算期間


last_notified: Dict[Tuple[str, str, str], datetime] = {}


def detect_events(
    symbol: str,
    timeframe: str,
    surge_rise_threshold: Optional[float] = 30.0,
    crash_drop_threshold: Optional[float] = 30.0,
    moving_average_short: int = MOVING_AVERAGE_SHORT,
    moving_average_middle: int = MOVING_AVERAGE_MIDDLE,
    moving_average_long: int = MOVING_AVERAGE_LONG,
    moving_average_method: str = MOVING_AVERAGE_METHOD,
) -> List[str]:
    """指定シンボルの移動平均と終値を取得し、クロス/暴騰/暴落を検知する

    引数:
        symbol: 銘柄名
        timeframe: 取得する時間足
        surge_rise_threshold: 暴騰検知を有効化する上昇幅。None で無効
        crash_drop_threshold: 暴落検知を有効化する下落幅。None で無効
        moving_average_short: 移動平均（短期）の期間設定
        moving_average_middle: 移動平均（中期）の期間設定
        moving_average_long: 移動平均（長期）の期間設定
        moving_average_method: 移動平均の算出方法 (SMA など)

    戻り値:
        検知したイベントを説明する文字列のリスト（検知なしは空リスト）。
    """
    events: List[str] = []

    # すべてのデータ（OHLCV + MA + RSI）を取得
    market_list_data = get_market_data(
        symbol=symbol,
        timeframe=timeframe,
        lookback_bars=GET_CHART_COUNT,
        moving_average_short=moving_average_short,
        moving_average_middle=moving_average_middle,
        moving_average_long=moving_average_long,
        moving_average_method=moving_average_method,
        price_source="CLOSE",
    )
    logger.info(
        "# %s %s MovingAverage(%s,%s,%s) %s",
        symbol,
        timeframe,
        moving_average_short,
        moving_average_middle,
        moving_average_long,
        moving_average_method,
    )
    # # RSIはEA計算結果を利用
    # if market_list_data:
    #     try:
    #         latest_rsi = float(market_list_data[-1]["rsi"])  # type: ignore[index]
    #         logger.info("RSI latest=%.2f", latest_rsi)
    #     except Exception:
    #         pass

    for market_data in market_list_data:
        rsi_val = market_data.get("rsi")
        rsi_display = f"{float(rsi_val):.2f}" if rsi_val is not None else "N/A"
        logger.info(
            (
                "[%s] open=%.5f high=%.5f low=%.5f close=%.5f  "
                "%s%s=%.5f  %s%s=%.5f  %s%s=%.5f  rsi=%s"
            ),
            market_data["time"].isoformat(timespec="seconds"),
            market_data["open"],
            market_data["high"],
            market_data["low"],
            market_data["close"],
            moving_average_method,
            moving_average_short,
            market_data["moving_average_short"],
            moving_average_method,
            moving_average_middle,
            market_data["moving_average_middle"],
            moving_average_method,
            moving_average_long,
            market_data["moving_average_long"],
            rsi_display,
        )

    if len(market_list_data) < 2:
        return events

    # チャートの状態を検知してテキストを作成する
    prev_market_data = market_list_data[-2]
    latest_market_data = market_list_data[-1]

    # デッドクロス検知
    if is_death_cross(
        prev_market_data["moving_average_short"],
        prev_market_data["moving_average_long"],
        latest_market_data["moving_average_short"],
        latest_market_data["moving_average_long"],
    ):
        key = (symbol, timeframe, "death")
        event_time = latest_market_data["time"]
        if last_notified.get(key) != event_time:
            last_notified[key] = event_time
            events.append(
                f"- {symbol}が{format_timeframe_label(timeframe)}でデッドクロス"
            )

    # ゴールデンクロス検知
    if is_golden_cross(
        prev_market_data["moving_average_short"],
        prev_market_data["moving_average_long"],
        latest_market_data["moving_average_short"],
        latest_market_data["moving_average_long"],
    ):
        key = (symbol, timeframe, "golden")
        event_time = latest_market_data["time"]
        if last_notified.get(key) != event_time:
            last_notified[key] = event_time
            events.append(
                f"- {symbol}が{format_timeframe_label(timeframe)}でゴールデンクロス"
            )

    # 暴騰検知
    if surge_rise_threshold is not None and is_price_surge(
        prev_market_data["close"], latest_market_data["close"], surge_rise_threshold
    ):
        key = (symbol, timeframe, "surge")
        event_time = latest_market_data["time"]
        if last_notified.get(key) != event_time:
            last_notified[key] = event_time
            rise_amount = latest_market_data["close"] - prev_market_data["close"]
            events.append(
                (
                    f"- {symbol}が{format_timeframe_label(timeframe)}で"
                    f"{rise_amount:.2f}ドル上昇 ({prev_market_data['close']:.2f}→{latest_market_data['close']:.2f})"
                )
            )

    # 暴落検知
    if crash_drop_threshold is not None and is_price_crash(
        prev_market_data["close"], latest_market_data["close"], crash_drop_threshold
    ):
        key = (symbol, timeframe, "crash")
        event_time = latest_market_data["time"]
        if last_notified.get(key) != event_time:
            last_notified[key] = event_time
            drop_amount = prev_market_data["close"] - latest_market_data["close"]
            events.append(
                (
                    f"- {symbol}が{format_timeframe_label(timeframe)}で"
                    f"{drop_amount:.2f}ドル下落 ({prev_market_data['close']:.2f}→{latest_market_data['close']:.2f})"
                )
            )

    return events


def main(
    target_data_list: List[Dict[str, Any]],
) -> None:
    """クロス検知を定期実行し検知内容を Slack へ通知する

    引数:
        なし

    戻り値:
        なし
    """
    try:
        while True:
            # 各銘柄・時間足ごとに検知を実行
            detected_events: List[str] = []
            for target_data in target_data_list:
                try:
                    # BTCUSD M5
                    events = detect_events(
                        symbol=target_data["symbol"],  # 銘柄名
                        timeframe=target_data["timeframe"],  # 取得する時間足
                        surge_rise_threshold=target_data[
                            "surge_rise_threshold"
                        ],  # 暴騰検知を有効化する上昇幅（ドル
                        crash_drop_threshold=target_data[
                            "crash_drop_threshold"
                        ],  # 暴落検知を有効化する下落幅（ドル）
                    )
                    detected_events.extend(events)
                except Exception as e:
                    logger.warning("ZECUSD detection failed: %s", e)
                    message = (
                        f"- {symbol}-{format_timeframe_label(timeframe)}: 検出失敗"
                    )
                    detected_events.append(message)

            # 検知内容をSlackへ通知
            if detected_events:
                message = "以下を検知しました\n\n" + "\n".join(detected_events)
                try:
                    notify_slack(
                        webhook_url=settings.slack_web_hook_url_moving_average_notification,  # noqa
                        message=message,
                    )
                    logger.info("Slack notified: %s", message)
                except Exception as notify_err:
                    logger.warning("Slack notification failed: %s", notify_err)

            if POLL_INTERVAL_SEC <= 0:
                break

            if DEBUG_MODE:
                logger.debug("sleep %s sec", POLL_INTERVAL_SEC)

            time.sleep(POLL_INTERVAL_SEC)
    except KeyboardInterrupt:
        logger.info("Stopped by user (Ctrl+C).")


if __name__ == "__main__":

    target_data_list = [
        {
            "symbol": "ZECUSD",
            "timeframe": "M5",
            "surge_rise_threshold": 30.0,
            "crash_drop_threshold": 30.0,
        },
        {
            "symbol": "ZECUSD",
            "timeframe": "M15",
            "surge_rise_threshold": 30.0,
            "crash_drop_threshold": 30.0,
        },
        {
            "symbol": "GOLD",
            "timeframe": "M5",
            "surge_rise_threshold": 30.0,
            "crash_drop_threshold": 30.0,
        },
        {
            "symbol": "GOLD",
            "timeframe": "M15",
            "surge_rise_threshold": 30.0,
            "crash_drop_threshold": 30.0,
        },
    ]
    main()

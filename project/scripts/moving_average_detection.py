"""
移動平均線を検知してslackへ通知を出す
銘柄や足など個別に対応可能

- ゴールデンクロス
- デッドクロス
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.custom_logger import setup_logger
from config.settings import Settings
from services.chart_service import (
    Row,
    format_timeframe_label,
    is_death_cross,
    is_golden_cross,
    is_price_crash,
    is_price_surge,
)
from services.mt5_service import (
    build_bridge_config,
    load_moving_average_csv,
    send_copy_moving_average,
)
from services.slack_service import notify_slack

settings = Settings()
logger = setup_logger(__name__, level=settings.log_level, fmt=settings.log_format)
POLL_INTERVAL_SEC: float = 60.0
DEBUG_MODE: bool = settings.debug_mode


last_notified: Dict[Tuple[str, str, str], datetime] = {}


def detect_symbol_cross_events(
    symbol: str,
    timeframe: str,
    count: int,
    moving_average_short: int,
    moving_average_middle: int,
    moving_average_long: int,
    moving_average_method: str,
    applied_price: str,
    timeout_sec: float,
    surge_rise_threshold: Optional[float] = None,
    crash_drop_threshold: Optional[float] = None,
) -> List[str]:
    """指定シンボルの移動平均と終値を取得し、クロス/暴騰/暴落を検知する

    Args:
        symbol: 銘柄名
        timeframe: 取得する時間足
        count: ブリッジに要求する本数
        moving_average_short: 移動平均（短期）の期間設定
        moving_average_middle: 移動平均（中期）の期間設定
        moving_average_long: 移動平均（長期）の期間設定
        moving_average_method: 移動平均の算出方法 (SMA など)
        applied_price: MT5 の価格種別
        timeout_sec: ブリッジ応答待ちのタイムアウト秒数
        surge_rise_threshold: 暴騰検知を有効化する上昇幅（ドル）。None で無効
        crash_drop_threshold: 暴落検知を有効化する下落幅（ドル）。None で無効
    """
    events: List[str] = []
    cfg = build_bridge_config(
        common_dir=Path(settings.mt5_common_dir),
        cmd_file_name=settings.mt5_cmd_file_name,
        resp_prefix=settings.mt5_resp_prefix,
    )

    def _fetch_rows(target_timeframe: str) -> List[Row]:
        csv_path = send_copy_moving_average(
            cfg,
            symbol=symbol,
            timeframe=target_timeframe,
            count=count,
            moving_average_short=moving_average_short,
            moving_average_middle=moving_average_middle,
            moving_average_long=moving_average_long,
            moving_average_method=moving_average_method,
            applied_price=applied_price,
            timeout_sec=timeout_sec,
        )
        fetched_rows = load_moving_average_csv(csv_path)
        try:
            csv_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as unlink_err:
            if DEBUG_MODE:
                logger.debug("failed to delete %s: %s", csv_path, unlink_err)
        return fetched_rows

    rows: List[Row] = _fetch_rows(timeframe)  # 古→新 で5本
    logger.info(
        "# %s %s MovingAverage(%s,%s,%s) %s/%s",
        symbol,
        timeframe,
        moving_average_short,
        moving_average_middle,
        moving_average_long,
        moving_average_method,
        applied_price,
    )
    for (
        t,
        close,
        moving_average_short_val,
        moving_average_middle_val,
        moving_average_long_val,
    ) in rows:
        timestamp_str = t.isoformat(timespec="seconds")
        logger.info(
            "[%s] close=%.5f  %s%s=%.5f  %s%s=%.5f  %s%s=%.5f",
            timestamp_str,
            close,
            moving_average_method,
            moving_average_short,
            moving_average_short_val,
            moving_average_method,
            moving_average_middle,
            moving_average_middle_val,
            moving_average_method,
            moving_average_long,
            moving_average_long_val,
        )

    # チャートの状態を検知してテキストを作成する
    if len(rows) >= 2:
        prev = rows[-2]
        latest = rows[-1]
        prev_close = prev[1]
        prev_moving_average_short = prev[2]
        prev_moving_average_long = prev[4]
        latest_close = latest[1]
        latest_moving_average_short = latest[2]
        latest_moving_average_long = latest[4]

        # デッドクロス検知
        if is_death_cross(
            prev_moving_average_short,
            prev_moving_average_long,
            latest_moving_average_short,
            latest_moving_average_long,
        ):
            key = (symbol, timeframe, "death")
            event_time = latest[0]
            if last_notified.get(key) != event_time:
                last_notified[key] = event_time
                events.append(
                    f"- {symbol}が{format_timeframe_label(timeframe)}でデッドクロス"
                )

        # ゴールデンクロス検知
        if is_golden_cross(
            prev_moving_average_short,
            prev_moving_average_long,
            latest_moving_average_short,
            latest_moving_average_long,
        ):
            key = (symbol, timeframe, "golden")
            event_time = latest[0]
            if last_notified.get(key) != event_time:
                last_notified[key] = event_time
                events.append(
                    f"- {symbol}が{format_timeframe_label(timeframe)}でゴールデンクロス"
                )

        # 暴騰検知
        if surge_rise_threshold is not None and is_price_surge(
            prev_close, latest_close, surge_rise_threshold
        ):
            key = (symbol, timeframe, "surge")
            event_time = latest[0]
            if last_notified.get(key) != event_time:
                last_notified[key] = event_time
                rise_amount = latest_close - prev_close
                events.append(
                    (
                        f"- {symbol}が{format_timeframe_label(timeframe)}で"
                        f"{rise_amount:.2f}ドル上昇 ({prev_close:.2f}→{latest_close:.2f})"
                    )
                )

        # 暴落検知
        if crash_drop_threshold is not None and is_price_crash(
            prev_close, latest_close, crash_drop_threshold
        ):
            key = (symbol, timeframe, "crash")
            event_time = latest[0]
            if last_notified.get(key) != event_time:
                last_notified[key] = event_time
                drop_amount = prev_close - latest_close
                events.append(
                    (
                        f"- {symbol}が{format_timeframe_label(timeframe)}で"
                        f"{drop_amount:.2f}ドル下落 ({prev_close:.2f}→{latest_close:.2f})"
                    )
                )

    return events


def detect_all_cross_events() -> List[str]:
    """登録済みシンボルすべてでクロス検知を実行し結果をまとめる"""
    detected_events: List[str] = []

    try:

        #
        events = detect_symbol_cross_events(
            symbol="ZECUSD",  # 銘柄名
            timeframe="M15",  # 取得する時間足
            count=5,  # ブリッジに要求する本数
            moving_average_short=5,  # 移動平均（短期）の期間設定
            moving_average_middle=20,  # 移動平均（中期）の期間設定
            moving_average_long=60,  # 移動平均（長期）の期間設定
            moving_average_method="SMA",  # 移動平均の算出方法 (SMA など)
            applied_price="CLOSE",  # MT5 の価格種別
            timeout_sec=20.0,  # ブリッジ応答待ちのタイムアウト秒数
            surge_rise_threshold=30.0,  # 暴騰検知を有効化する上昇幅（ドル
            crash_drop_threshold=30.0,  # 暴落検知を有効化する下落幅（ドル）
        )
        detected_events.extend(events)
    except Exception as e:
        logger.warning("ZECUSD detection failed: %s", e)

    try:
        events = detect_symbol_cross_events(
            symbol="GOLD",  # 銘柄名
            timeframe="M15",  # 取得する時間足
            count=5,  # ブリッジに要求する本数
            moving_average_short=5,  # 移動平均（短期）の期間設定
            moving_average_middle=20,  # 移動平均（中期）の期間設定
            moving_average_long=60,  # 移動平均（長期）の期間設定
            moving_average_method="SMA",  # 移動平均の算出方法 (SMA など)
            applied_price="CLOSE",  # MT5 の価格種別
            timeout_sec=20.0,  # ブリッジ応答待ちのタイムアウト秒数
            surge_rise_threshold=30.0,  # 暴騰検知を有効化する上昇幅（ドル
            crash_drop_threshold=30.0,  # 暴落検知を有効化する下落幅（ドル）
        )
        detected_events.extend(events)
    except Exception as e:
        logger.warning("GOLD detection failed: %s", e)

    return detected_events


def main() -> None:
    """クロス検知を定期実行し検知内容を Slack へ通知する"""
    try:
        while True:
            detected_events = detect_all_cross_events()

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
    main()

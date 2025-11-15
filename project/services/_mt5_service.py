from __future__ import annotations

import csv
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, TypedDict, cast

from config.custom_logger import setup_logger
from config.settings import Settings

settings = Settings()
logger = setup_logger(__name__, level=settings.log_level, fmt=settings.log_format)


class BridgeConfig(TypedDict):
    common_dir: Path
    cmd_file_name: str
    resp_prefix: str


def build_bridge_config(
    common_dir: Path, cmd_file_name: str, resp_prefix: str
) -> BridgeConfig:
    """ブリッジ操作で使う共通設定を辞書化して返す

    Args:
        common_dir: MT5 共有ディレクトリ
        cmd_file_name: EA が監視するコマンドファイル名
        resp_prefix: EA のレスポンスファイル接頭辞
    """
    return {
        "common_dir": common_dir,
        "cmd_file_name": cmd_file_name,
        "resp_prefix": resp_prefix,
    }


def send_copy_moving_average(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    moving_average_short: int,
    moving_average_middle: int,
    moving_average_long: int,
    moving_average_method: str,
    applied_price: str = "CLOSE",
    get_chart_count: int = 5,
) -> Path:
    """ブリッジ経由で MT5 に移動平均を取得し CSV パスを返す

    Args:
        cfg: ブリッジ設定
        symbol: 対象銘柄
        timeframe: 取得する時間足
        count: 要求するバーの本数
        moving_average_short: 短期移動平均の期間
        moving_average_middle: 中期移動平均の期間
        moving_average_long: 長期移動平均の期間
        moving_average_method: 移動平均の算出方法（SMA など MT5 定義）
        applied_price: 適用価格種別（CLOSE など）
        get_chart_count: 取得するチャートバーの本数
    """
    cmd_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
    )
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "COPY_MA",
        "symbol": symbol,
        "timeframe": timeframe,
        "count": str(get_chart_count),
        "period_short": str(moving_average_short),
        "period_middle": str(moving_average_middle),
        "period_long": str(moving_average_long),
        "method": moving_average_method,
        "applied_price": applied_price,
    }

    logger.debug(
        "send COPY_MA id=%s %s %s count=%s",
        cmd_id,
        symbol,
        timeframe,
        get_chart_count,
    )

    common_dir = cast(Path, cfg["common_dir"])
    cmd_file_name = cast(str, cfg["cmd_file_name"])
    _write_kv_file(common_dir / cmd_file_name, kv)
    resp = _wait_resp(cfg, cmd_id)

    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")

    csv_name = resp.get("data_file", "")
    if not csv_name:
        raise RuntimeError("EA response missing 'data_file'")
    csv_path = common_dir / csv_name

    for _ in range(20):
        if csv_path.exists():
            break
        time.sleep(0.05)

    if not csv_path.exists():
        raise RuntimeError(f"csv not found: {csv_path}")
    return csv_path


def load_moving_average_csv(
    csv_path: Path,
) -> List[Tuple[datetime, float, float, float, float]]:
    """移動平均 CSV を読み込み Row リストへ変換する

    CSV列: time,close,ma_short,ma_middle,ma_long
    戻り: [(時刻UTC, close, moving_average_short, moving_average_middle, moving_average_long), ...]（古→新）

    Args:
        csv_path: MT5 から出力された移動平均 CSV のパス
    """  # noqa: E501
    out: List[Tuple[datetime, float, float, float, float]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = _parse_mt5_time(row["time"])
            close = float(row["close"])
            moving_average_short = float(row["ma_short"])
            moving_average_middle = float(row["ma_middle"])
            moving_average_long = float(row["ma_long"])
            out.append(
                (
                    t,
                    close,
                    moving_average_short,
                    moving_average_middle,
                    moving_average_long,
                )
            )
    return out


# ===== レート（OHLCV）取得 ===== #

RatesRow = Tuple[datetime, float, float, float, float, int, int, int]


def send_copy_rates(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    get_chart_count: int = 300,
) -> Path:
    """ブリッジ経由で MT5 にレート（OHLCV）CSV の生成を依頼しパスを返す

    Args:
        cfg: ブリッジ設定
        symbol: 対象銘柄
        timeframe: 取得する時間足
        get_chart_count: 取得するチャートバーの本数
    """
    cmd_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
    )
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "COPY_RATES",
        "symbol": symbol,
        "timeframe": timeframe,
        "count": str(get_chart_count),
    }

    logger.debug(
        "send COPY_RATES id=%s %s %s count=%s",
        cmd_id,
        symbol,
        timeframe,
        get_chart_count,
    )

    common_dir = cast(Path, cfg["common_dir"])
    cmd_file_name = cast(str, cfg["cmd_file_name"])
    _write_kv_file(common_dir / cmd_file_name, kv)
    resp = _wait_resp(cfg, cmd_id)

    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")

    csv_name = resp.get("data_file", "")
    if not csv_name:
        raise RuntimeError("EA response missing 'data_file'")
    csv_path = common_dir / csv_name

    for _ in range(20):
        if csv_path.exists():
            break
        time.sleep(0.05)

    if not csv_path.exists():
        raise RuntimeError(f"csv not found: {csv_path}")
    return csv_path


def load_rates_csv(csv_path: Path) -> List[RatesRow]:
    """レートCSV（time,open,high,low,close,tick_volume,spread,real_volume）を読み込む

    Args:
        csv_path: MT5 から出力されたレート CSV のパス
    """
    out: List[RatesRow] = []
    with csv_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = _parse_mt5_time(row["time"])
            o = float(row["open"])  # noqa: E741
            h = float(row["high"])  # noqa: E741
            l = float(row["low"])  # noqa: E741
            c = float(row["close"])  # noqa: E741
            tv = int(float(row.get("tick_volume", "0")))
            sp = int(float(row.get("spread", "0")))
            rv = int(float(row.get("real_volume", "0")))
            out.append((t, o, h, l, c, tv, sp, rv))
    return out


# ===== MA/RSI の最新値取得（CSV不要） ===== #


def send_get_moving_average_latest(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    moving_average_short: int,
    moving_average_middle: int,
    moving_average_long: int,
    moving_average_method: str,
    applied_price: str = "CLOSE",
    ma_shift: int = 1,
) -> Tuple[datetime, float, float, float, float]:
    """最新バー（もしくは確定バー）の短/中/長MA値と終値を返す

    Args:
        cfg: ブリッジ設定
        symbol: 対象銘柄
        timeframe: 取得する時間足
        moving_average_short: 短期移動平均の期間
        moving_average_middle: 中期移動平均の期間
        moving_average_long: 長期移動平均の期間
        moving_average_method: 移動平均の算出方法（SMA など）
        applied_price: 適用価格種別（CLOSE など）
        ma_shift: 0=未確定バー / 1=確定バー（既定）
    戻り値:
        (bar_timeUTC, close, ma_short, ma_middle, ma_long)
    """
    cmd_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
    )
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "GET_MA_LATEST",
        "symbol": symbol,
        "timeframe": timeframe,
        "period_short": str(moving_average_short),
        "period_middle": str(moving_average_middle),
        "period_long": str(moving_average_long),
        "method": moving_average_method,
        "applied_price": applied_price,
        "ma_shift": str(ma_shift),
    }

    logger.debug(
        "send GET_MA_LATEST id=%s %s %s S/M/L=(%s,%s,%s) %s %s shift=%s",
        cmd_id,
        symbol,
        timeframe,
        moving_average_short,
        moving_average_middle,
        moving_average_long,
        moving_average_method,
        applied_price,
        ma_shift,
    )

    common_dir = cast(Path, cfg["common_dir"])
    cmd_file_name = cast(str, cfg["cmd_file_name"])
    _write_kv_file(common_dir / cmd_file_name, kv)
    resp = _wait_resp(cfg, cmd_id)

    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")

    bar_time = _parse_mt5_time(resp["bar_time"])
    close = float(resp["close"])  # noqa: E741
    ma_s = float(resp["ma_short"])  # noqa: E741
    ma_m = float(resp["ma_middle"])  # noqa: E741
    ma_l = float(resp["ma_long"])  # noqa: E741
    return (bar_time, close, ma_s, ma_m, ma_l)


def send_get_rsi_latest(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    period: int = 14,
    applied_price: str = "CLOSE",
    ma_shift: int = 1,
) -> Tuple[datetime, float, float]:
    """最新バー（もしくは確定バー）のRSIと終値を返す

    Args:
        cfg: ブリッジ設定
        symbol: 対象銘柄
        timeframe: 取得する時間足
        period: RSI の期間
        applied_price: 適用価格種別（CLOSE など）
        ma_shift: 0=未確定バー / 1=確定バー（既定）
    戻り値:
        (bar_timeUTC, close, rsi)
    """
    cmd_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
    )
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "GET_RSI_LATEST",
        "symbol": symbol,
        "timeframe": timeframe,
        # EA側は period_short をRSI期間として参照
        "period_short": str(period),
        "applied_price": applied_price,
        "ma_shift": str(ma_shift),
    }

    logger.debug(
        "send GET_RSI_LATEST id=%s %s %s period=%s %s shift=%s",
        cmd_id,
        symbol,
        timeframe,
        period,
        applied_price,
        ma_shift,
    )

    common_dir = cast(Path, cfg["common_dir"])
    cmd_file_name = cast(str, cfg["cmd_file_name"])
    _write_kv_file(common_dir / cmd_file_name, kv)
    resp = _wait_resp(cfg, cmd_id)

    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")

    bar_time = _parse_mt5_time(resp["bar_time"])
    close = float(resp["close"])  # noqa: E741
    rsi = float(resp["rsi"])  # noqa: E741
    return (bar_time, close, rsi)


def send_copy_rsi(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    period: int = 14,
    applied_price: str = "CLOSE",
    get_chart_count: int = 300,
) -> Path:
    """ブリッジ経由で MT5 にRSIシリーズCSVの生成を依頼しパスを返す

    Args:
        cfg: ブリッジ設定
        symbol: 対象銘柄
        timeframe: 取得する時間足
        period: RSI の期間
        applied_price: 適用価格種別（CLOSE など）
        get_chart_count: 取得するチャートバーの本数
    """
    cmd_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:6]
    )
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "COPY_RSI",
        "symbol": symbol,
        "timeframe": timeframe,
        # EA側の仕様に合わせ period_short をRSI期間として送る
        "period_short": str(period),
        "applied_price": applied_price,
        "count": str(get_chart_count),
    }

    logger.debug(
        "send COPY_RSI id=%s %s %s period=%s %s count=%s",
        cmd_id,
        symbol,
        timeframe,
        period,
        applied_price,
        get_chart_count,
    )

    common_dir = cast(Path, cfg["common_dir"])
    cmd_file_name = cast(str, cfg["cmd_file_name"])
    _write_kv_file(common_dir / cmd_file_name, kv)
    resp = _wait_resp(cfg, cmd_id)

    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")

    csv_name = resp.get("data_file", "")
    if not csv_name:
        raise RuntimeError("EA response missing 'data_file'")
    csv_path = common_dir / csv_name

    for _ in range(20):
        if csv_path.exists():
            break
        time.sleep(0.05)

    if not csv_path.exists():
        raise RuntimeError(f"csv not found: {csv_path}")
    return csv_path


def load_rsi_csv(csv_path: Path) -> List[Tuple[datetime, float, float]]:
    """RSI CSV（time,close,rsi）を読み込む

    Args:
        csv_path: MT5 から出力された RSI CSV のパス
    """
    out: List[Tuple[datetime, float, float]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            t = _parse_mt5_time(row["time"])
            close = float(row["close"])  # noqa: E741
            rsi = float(row["rsi"])  # noqa: E741
            out.append((t, close, rsi))
    return out


# ===== 高レベル: CSVを取得してデータを返す（片付け込み） ===== #


def copy_and_load_moving_average(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    moving_average_short: int,
    moving_average_middle: int,
    moving_average_long: int,
    moving_average_method: str,
    applied_price: str = "CLOSE",
    get_chart_count: int = 300,
) -> List[Tuple[datetime, float, float, float, float]]:
    """MT5にCOPY_MAを依頼してCSVを受け取り、解析して返す（古→新）。

    返却: [(timeUTC, close, ma_short, ma_middle, ma_long), ...]
    """
    csv_path = send_copy_moving_average(
        cfg,
        symbol=symbol,
        timeframe=timeframe,
        moving_average_short=moving_average_short,
        moving_average_middle=moving_average_middle,
        moving_average_long=moving_average_long,
        moving_average_method=moving_average_method,
        applied_price=applied_price,
        get_chart_count=get_chart_count,
    )
    rows = load_moving_average_csv(csv_path)
    try:
        csv_path.unlink()
    except OSError:
        pass
    return rows


def copy_and_load_rates(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    get_chart_count: int = 300,
) -> List[RatesRow]:
    """MT5にCOPY_RATESを依頼してCSVを受け取り、解析して返す（古→新）。

    返却: [(timeUTC, open, high, low, close, tick_volume, spread, real_volume), ...]
    """
    csv_path = send_copy_rates(
        cfg,
        symbol=symbol,
        timeframe=timeframe,
        get_chart_count=get_chart_count,
    )
    rows = load_rates_csv(csv_path)
    try:
        csv_path.unlink()
    except OSError:
        pass
    return rows


def copy_and_load_rsi(
    cfg: BridgeConfig,
    symbol: str,
    timeframe: str,
    period: int = 14,
    applied_price: str = "CLOSE",
    get_chart_count: int = 300,
) -> List[Tuple[datetime, float, float]]:
    """MT5にCOPY_RSIを依頼してCSVを受け取り、解析して返す（古→新）。

    返却: [(timeUTC, close, rsi), ...]
    """
    csv_path = send_copy_rsi(
        cfg,
        symbol=symbol,
        timeframe=timeframe,
        period=period,
        applied_price=applied_price,
        get_chart_count=get_chart_count,
    )
    rows = load_rsi_csv(csv_path)
    try:
        csv_path.unlink()
    except OSError:
        pass
    return rows


def _wait_resp(
    cfg: BridgeConfig,
    cmd_id: str,
) -> Dict[str, str]:
    """EA のレスポンスファイルをタイムアウトまでポーリングする

    Args:
        cfg: ブリッジ設定
        cmd_id: リクエスト ID
    """
    # 待機秒
    timeout = 20.0

    common_dir = cast(Path, cfg["common_dir"])
    resp_prefix = cast(str, cfg["resp_prefix"])
    end = time.monotonic() + timeout
    resp = common_dir / f"{resp_prefix}{cmd_id}.txt"

    logger.debug("wait_resp: %s", resp)
    while time.monotonic() < end:
        if resp.exists():
            data = _read_kv_file(resp)
            try:
                resp.unlink()
            except OSError:
                pass
            logger.debug("resp data=%s", data)
            return data
        time.sleep(0.1)
    raise TimeoutError("timeout")


def _write_kv_file(path: Path, kv: Dict[str, str]) -> None:
    """MT5 コマンドファイルへ key=value をアトミックに書き込む

    Args:
        path: 書き込み先ファイル
        kv: 出力する key/value ペア
    """
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")
    tmp.replace(path)


def _read_kv_file(path: Path) -> Dict[str, str]:
    """MT5 形式の key=value テキストを辞書に変換する

    Args:
        path: 読み込み対象ファイル
    """
    out: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _parse_mt5_time(cell: str) -> datetime:
    """MT5 CSV の時刻文字列をタイムゾーン付き datetime へ変換する

    Args:
        cell: MT5 形式の時刻セル文字列
    """
    cell = cell.strip()
    try:
        return datetime.fromtimestamp(int(float(cell)), tz=timezone.utc)
    except ValueError:
        pass
    try:
        dt = datetime.strptime(cell, "%Y.%m.%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        dt = datetime.strptime(cell, "%Y.%m.%d %H:%M:%S.%f")
        return dt.replace(tzinfo=timezone.utc)

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import csv

from config.custom_logger import setup_logger
from config.settings import Settings

settings = Settings()
logger = setup_logger(__name__, level=settings.log_level, fmt=settings.log_format)


def get_market_data(
    symbol: str,
    timeframe: str,
    lookback_bars: int,
    moving_average_short: int,
    moving_average_middle: int,
    moving_average_long: int,
    moving_average_method: str,
    price_source: str,
    common_dir: Optional[str] = None,
    cmd_file_name: Optional[str] = None,
    resp_prefix: Optional[str] = None,
) -> List[Dict[str, object]]:
    """MT5 EA（COPY_MA）経由で相場の「全部入り」データを取得する。

    概要:
        - ローソク（OHLCV: time, open, high, low, close, tick_volume, spread, real_volume）
        - インジケータ（移動平均: 短/中/長、RSI）
        を1行=1辞書の配列（古→新）で返します。CSV生成→読込→削除まで内部で実施します。

    引数:
        symbol: 銘柄名（例: "GOLD"）
        timeframe: 取得する時間足（例: "M5", "H1"）
        lookback_bars: 取得するバー本数（末尾が最新。0以下はEA側の全バー）
        moving_average_short: 移動平均（短期）の期間
        moving_average_middle: 移動平均（中期）の期間
        moving_average_long: 移動平均（長期）の期間
        moving_average_method: 移動平均の算出方法（SMA/EMA/SMMA/LWMA）
        price_source: インジケータの適用価格（CLOSE/OPEN/HIGH/LOW/...）
        common_dir: MT5の共有ディレクトリ。未指定時は Settings.mt5_common_dir を使用
        cmd_file_name: コマンドファイル名。未指定時は Settings.mt5_cmd_file_name を使用
        resp_prefix: 応答ファイル接頭辞。未指定時は Settings.mt5_resp_prefix を使用

    戻り値:
        time, open, high, low, close, tick_volume, spread, real_volume,
        moving_average_short, moving_average_middle, moving_average_long, rsi
        をキーに持つ辞書の配列。
    """

    common_dir = Path(common_dir) if common_dir else None
    operator_mt5 = OperatorMT5(
        common_dir or Path(settings.mt5_common_dir),
        cmd_file_name or settings.mt5_cmd_file_name,
        resp_prefix or settings.mt5_resp_prefix,
    )

    csv_path = operator_mt5.copy_bars_full_path(
        symbol,
        timeframe,
        lookback_bars,
        moving_average_short,
        moving_average_middle,
        moving_average_long,
        moving_average_method,
        price_source,
    )

    return _load_bars_full_csv(csv_path)


def order_send(
    symbol: str,
    order_type: str,
    volume: float,
    sl: float = 0.0,
    tp: float = 0.0,
    deviation: int = 10,
    comment: str = "",
    common_dir: Optional[str] = None,
    cmd_file_name: Optional[str] = None,
    resp_prefix: Optional[str] = None,
) -> Dict[str, str]:
    """MT5 EA（ORDER_SEND）で成行のBUY/SELL注文を送信する。

    概要:
        EAへ成行注文を発行し、チケット番号や約定価格などの結果を辞書で返します。
        端末側の自動売買設定やシンボル取引許可が必要です。

    引数:
        symbol: 銘柄名
        order_type: "BUY" または "SELL"
        volume: 取引数量（ロット）
        sl: 損切りの価格（0で未設定）
        tp: 利確の価格（0で未設定）
        deviation: 許容スリッページ（ポイント）
        comment: 注文コメント
        common_dir: MT5の共有ディレクトリ。未指定時は Settings.mt5_common_dir を使用
        cmd_file_name: コマンドファイル名。未指定時は Settings.mt5_cmd_file_name を使用
        resp_prefix: 応答ファイル接頭辞。未指定時は Settings.mt5_resp_prefix を使用

    戻り値:
        応答辞書（例: {"ok":"true","ticket":"...","retcode":"...","price":"..."}）
    """
    common_dir = Path(common_dir) if common_dir else None
    operator_mt5 = OperatorMT5(
        common_dir or Path(settings.mt5_common_dir),
        cmd_file_name or settings.mt5_cmd_file_name,
        resp_prefix or settings.mt5_resp_prefix,
    )

    cmd_id = operator_mt5.new_id()
    kv: Dict[str, str] = {
        "id": cmd_id,
        "action": "ORDER_SEND",
        "symbol": symbol,
        "type": order_type,
        "volume": str(volume),
        "sl": str(sl),
        "tp": str(tp),
        "deviation": str(deviation),
        "comment": comment,
    }
    resp = operator_mt5.send(kv)
    if resp.get("ok", "false").lower() != "true":
        raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")
    # 返却例: { ok=true, id=..., ticket=..., retcode=..., price=... }
    return resp


def _load_bars_full_csv(csv_path: Path) -> List[Dict[str, object]]:
    """
    CSV（ローソク＋MA＋RSI）を読み込み、1行=1辞書の配列で返す。

    csvのヘッダー
    time,open,high,low,close,tick_volume,spread,real_volume,moving_average_short,moving_average_middle,moving_average_long,rsi

    """
    out: List[Dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            rec: Dict[str, object] = {}
            rec["time"] = OperatorMT5._parse_mt5_time(row.get("time", ""))
            for k in (
                "open",
                "high",
                "low",
                "close",
                "moving_average_short",
                "moving_average_middle",
                "moving_average_long",
                "rsi",
            ):
                v = row.get(k)
                if v is not None and v != "":
                    rec[k] = float(v)
            for k in ("tick_volume", "spread", "real_volume"):
                v = row.get(k)
                if v is not None and v != "":
                    rec[k] = int(float(v))
            for k, v in row.items():
                if k not in rec and k != "time" and v is not None:
                    rec[k] = v
            out.append(rec)
    return out


class OperatorMT5:
    """MT5 とファイル越し（Common/Files）でやり取りするための小さなヘルパ。

    - コマンドを書いたテキスト（key=value）を `common_dir/cmd_file_name` に出力
    - EA は同コマンドを処理し、`resp_prefix + id + .txt` に応答を返す
    - CSV を出力する系は、応答ファイルの `data_file` にCSVファイル名が入る

    主な公開メソッド:
    - get_market_data: そのCSVを読み込み、ローソクデータ、移動平均線、RSIなどを辞書配列で返す
    - order_send: 成行で BUY/SELL を発注
    """

    # 既定タイムアウト（全インスタンスで共有）
    DEFAULT_TIMEOUT_SEC: float = 20.0

    def __init__(
        self,
        common_dir: Path,
        cmd_file_name: str,
        resp_prefix: str,
    ) -> None:
        """ブリッジの入出力に使うパス/ファイル名/プレフィクスを設定する。

        Args:
            common_dir: MT5 の Common/Files にマウントされた共有ディレクトリ
            cmd_file_name: EA が監視するコマンドファイル名（例: mt5_cmd.txt）
            resp_prefix: 応答ファイルの接頭辞（例: mt5_resp_）
        """
        self.common_dir = common_dir
        self.cmd_file_name = cmd_file_name
        self.resp_prefix = resp_prefix

    def new_id(self) -> str:
        """リクエストIDを生成（UTC時刻+短い乱数）。"""
        return (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_")
            + uuid.uuid4().hex[:6]
        )

    def send(self, kv: Dict[str, str]) -> Dict[str, str]:
        """コマンドファイルへ key=value を書き、応答を待つ。"""
        self._write_kv_file(kv)
        return self._wait(kv["id"])

    def copy_bars_full_path(
        self,
        symbol: str,
        timeframe: str,
        lookback_bars: int,
        moving_average_short: int,
        moving_average_middle: int,
        moving_average_long: int,
        moving_average_method: str,
        price_source: str,
    ) -> Path:
        """全部入りCSV（ローソク+MA+RSI）を生成させ、そのファイルパスを返す（内部用）。

        EA 側の `COPY_MA` が time,open,high,low,close,tick_volume,spread,real_volume,
        moving_average_short,moving_average_middle,moving_average_long,rsi の
        列を持つCSVを出力します。

        Args:
            symbol: 取得する銘柄名（例: "GOLD"）
            timeframe: 時間足（例: "M15", "H1", ...）
            lookback_bars: 取得するバー本数（末尾が最新。0以下はEA側で全バー）
            moving_average_short: 短期MAの期間
            moving_average_middle: 中期MAの期間
            moving_average_long: 長期MAの期間
            moving_average_method: 移動平均線の算出方法（SMA/EMA/SMMA/LWMA）
            price_source: インジケータの適用価格（CLOSE/OPEN/HIGH/LOW/...）

        Returns:
            生成されたCSVの `Path`。実体が出るまで短時間ポーリングします。
        """
        cmd_id = self.new_id()
        kv: Dict[str, str] = {
            "id": cmd_id,
            "action": "COPY_MA",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": str(lookback_bars),
            "period_short": str(moving_average_short),
            "period_middle": str(moving_average_middle),
            "period_long": str(moving_average_long),
            "method": moving_average_method,
            "applied_price": price_source,
        }
        logger.debug(
            "send COPY_MA(full) id=%s %s %s count=%s",
            cmd_id,
            symbol,
            timeframe,
            lookback_bars,
        )
        resp = self.send(kv)
        if resp.get("ok", "false").lower() != "true":
            raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")
        csv_name = resp.get("data_file", "")
        if not csv_name:
            raise RuntimeError("EA response missing 'data_file'")
        csv_path = self.common_dir / csv_name
        for _ in range(20):
            if csv_path.exists():
                break
            time.sleep(0.05)
        if not csv_path.exists():
            raise RuntimeError(f"csv not found: {csv_path}")
        return csv_path

    def _wait(self, cmd_id: str) -> Dict[str, str]:
        """応答ファイル（mt5_resp_<id>.txt）が現れるまで既定秒待つ。"""
        return self._wait_resp(cmd_id, type(self).DEFAULT_TIMEOUT_SEC)

    def _write_kv_file(self, kv: Dict[str, str]) -> None:
        """コマンドファイルを書き換え時衝突を避けるため一時ファイル→置換で書く。"""
        path = self.common_dir / self.cmd_file_name
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")
        tmp.replace(path)

    def _wait_resp(self, cmd_id: str, timeout_sec: float) -> Dict[str, str]:
        """指定IDの応答ファイルをポーリングで待ち、辞書化して返す。"""
        end = time.monotonic() + timeout_sec
        resp = self.common_dir / f"{self.resp_prefix}{cmd_id}.txt"
        logger.debug("wait_resp: %s", resp)
        while time.monotonic() < end:
            if resp.exists():
                data = self._read_kv_file(resp)
                try:
                    resp.unlink()
                except OSError:
                    pass
                logger.debug("resp data=%s", data)
                return data
            time.sleep(0.1)
        raise TimeoutError("timeout")

    @staticmethod
    def _read_kv_file(path: Path) -> Dict[str, str]:
        """key=value 形式ファイルを辞書に変換する（空行/不正行はスキップ）。"""
        out: Dict[str, str] = {}
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
        return out

    @staticmethod
    def _parse_mt5_time(cell: str) -> datetime:
        """MT5の時刻セルをUTCのdatetimeへ変換（POSIX秒/日付文字列の双方に対応）。"""
        s = cell.strip()
        try:
            return datetime.fromtimestamp(int(float(s)), tz=timezone.utc)
        except ValueError:
            pass
        try:
            dt = datetime.strptime(s, "%Y.%m.%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            dt = datetime.strptime(s, "%Y.%m.%d %H:%M:%S.%f")
            return dt.replace(tzinfo=timezone.utc)

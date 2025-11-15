from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, cast
import csv

from config.custom_logger import setup_logger
from config.settings import Settings

settings = Settings()
logger = setup_logger(__name__, level=settings.log_level, fmt=settings.log_format)


class OperatorMT5:
    """MT5 とファイル越し（Common/Files）でやり取りするための小さなヘルパ。

    - コマンドを書いたテキスト（key=value）を `common_dir/cmd_file_name` に出力
    - EA は同コマンドを処理し、`resp_prefix + id + .txt` に応答を返す
    - CSV を出力する系は、応答ファイルの `data_file` にCSVファイル名が入る

    主な公開メソッド:
    - copy_bars_full: そのCSVを読み込み、辞書配列で返す（CSVは削除）
    - symbol_info_tick: ティック情報（bid/ask/last/time）を取得
    - order_send: 成行で BUY/SELL を発注

    タイムアウトはクラス変数 `DEFAULT_TIMEOUT_SEC` を用います。
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

    # ========== データ取得（全部入りCSV） ==========
    def _copy_bars_full_path(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        period_short: int,
        period_middle: int,
        period_long: int,
        method: str,
        applied_price: str,
    ) -> Path:
        """全部入りCSV（ローソク+MA+RSI）を生成させ、そのファイルパスを返す（内部用）。

        EA 側の `COPY_MA` が time,open,high,low,close,tick_volume,spread,real_volume,
        moving_average_short,moving_average_middle,moving_average_long,rsi の
        列を持つCSVを出力します。

        Args:
            symbol: 取得する銘柄名（例: "GOLD"）
            timeframe: 時間足（例: "M15", "H1", ...）
            count: 取得するバー本数（末尾が最新。0以下はEA側で全バー）
            period_short: 短期MAの期間
            period_middle: 中期MAの期間
            period_long: 長期MAの期間
            method: MAの算出方法（SMA/EMA/SMMA/LWMA）
            applied_price: MA/RSIの適用価格（CLOSE/OPEN/HIGH/LOW/...）

        Returns:
            生成されたCSVの `Path`。実体が出るまで短時間ポーリングします。
        """
        cmd_id = self._new_id()
        kv: Dict[str, str] = {
            "id": cmd_id,
            "action": "COPY_MA",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": str(count),
            "period_short": str(period_short),
            "period_middle": str(period_middle),
            "period_long": str(period_long),
            "method": method,
            "applied_price": applied_price,
        }
        logger.debug(
            "send COPY_MA(full) id=%s %s %s count=%s",
            cmd_id,
            symbol,
            timeframe,
            count,
        )
        resp = self._send(kv)
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

    def copy_bars_full(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        period_short: int,
        period_middle: int,
        period_long: int,
        method: str,
        applied_price: str,
    ) -> List[Dict[str, object]]:
        """全部入りCSVを読み込み、1行=1辞書の配列で返す（CSVは削除）。

        Returns:
            以下のキーを持つ辞書の配列（古→新）:
            - time(datetime, UTC), open(float), high(float), low(float), close(float)
            - tick_volume(int), spread(int), real_volume(int)
            - moving_average_short(float), moving_average_middle(float), moving_average_long(float)
            - rsi(float)
        """
        path = self._copy_bars_full_path(
            symbol,
            timeframe,
            count,
            period_short,
            period_middle,
            period_long,
            method,
            applied_price,
        )
        try:
            return self.load_bars_full_csv(path)
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    # ========== ティック情報 ==========
    def symbol_info_tick(self, symbol: str) -> Dict[str, str]:
        """最新ティック情報を取得する。

        Args:
            symbol: 対象銘柄

        Returns:
            応答辞書（例: {"ok":"true","symbol":"...","bid":"...",
            "ask":"...","last":"...","time":"POSIX秒"}）
        """
        cmd_id = self._new_id()
        kv: Dict[str, str] = {
            "id": cmd_id,
            "action": "SYMBOL_INFO_TICK",
            "symbol": symbol,
        }
        resp = self._send(kv)
        if resp.get("ok", "false").lower() != "true":
            raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")
        return resp

    # ========== 成行注文 ==========
    def order_send(
        self,
        symbol: str,
        order_type: str,  # "BUY" or "SELL"
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        deviation: int = 10,
        comment: str = "",
    ) -> Dict[str, str]:
        """成行注文（BUY/SELL）を送信する。

        Args:
            symbol: 銘柄名
            order_type: "BUY" もしくは "SELL"
            volume: 取引数量（ロット）
            sl: 損切りの価格（0 で未設定）
            tp: 利確の価格（0 で未設定）
            deviation: 許容スリッページ（ポイント）
            comment: 注文コメント

        Returns:
            応答辞書（例: {"ok":"true","ticket":"...","retcode":"...",
            "price":"..."}）。失敗時は例外。
        """
        cmd_id = self._new_id()
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
        resp = self._send(kv)
        if resp.get("ok", "false").lower() != "true":
            raise RuntimeError(f"EA error: {resp.get('error', 'unknown')}")
        # 返却例: { ok=true, id=..., ticket=..., retcode=..., price=... }
        return resp

    # ========== 基本ユーティリティ ==========
    def _new_id(self) -> str:
        """リクエストIDを生成（UTC時刻+短い乱数）。"""
        return (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_")
            + uuid.uuid4().hex[:6]
        )

    def _wait(self, cmd_id: str) -> Dict[str, str]:
        """応答ファイル（mt5_resp_<id>.txt）が現れるまで既定秒待つ。"""
        return self._wait_resp(cmd_id, type(self).DEFAULT_TIMEOUT_SEC)

    def _send(self, kv: Dict[str, str]) -> Dict[str, str]:
        """コマンドファイルへ key=value を書き、応答を待つ。"""
        self._write_kv_file(kv)
        return self._wait(kv["id"])

    # ---- 内部: ファイルI/O / 応答待ち ----
    def _write_kv_file(self, kv: Dict[str, str]) -> None:
        """コマンドファイルを書き換え時衝突を避けるため一時ファイル→置換で書く。"""
        path = self.common_dir / self.cmd_file_name
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")
        tmp.replace(path)

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

    @staticmethod
    def load_bars_full_csv(csv_path: Path) -> List[Dict[str, object]]:
        """全部入りCSV（ローソク＋MA＋RSI）を読み込み、1行=1辞書の配列で返す。"""
        out: List[Dict[str, object]] = []
        with csv_path.open("r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                rec: Dict[str, object] = {}
                rec["time"] = MT5._parse_mt5_time(row.get("time", ""))
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

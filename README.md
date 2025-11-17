# 概要

株取引である MT5 を監視してゴールデンクロス、デッドクロスなどを検知して slack へ通知を出すプログラムを作りました

ゴールデンクロス、デッドクロスが発生すると、株の流れが大きく変わることが多いため検知できると有利だと考えたからです

制約

- MT5 は Windows 上で動かす必要がある
- Mt5 のアカウントは作成する必要がある
- Mt5 に適切に設定をする必要がある
- 今回のプログラムでは WSL 上の Docker 環境で動かすことを想定

# 仕組み

今回作成した仕組みは以下の通りです

1. MT5 上で`docs/MT5で行う設定/WSL_FileBridge.mq5`を常時実行しておく
   a. `/mnt/c/Users/campbel/AppData/Roaming/MetaQuotes/Terminal/Common/Files`に移動平均線のデータがユニークな id 付きの csv で保存される
   b. 例) `mt5_ma_20251113T165918Z_8fdf77.csv`

2. `/mnt/c/Users/campbel/AppData/Roaming/MetaQuotes/Terminal/Common/Files`に作成されたファイルを WSL 上の Python から定期的に読み取り移動平均線のデータを取得して解析を行う

図で表すと以下の通り

<img src="https://github.com/campbel2525/sample-mt5/blob/main/docs/%E6%A7%8B%E6%88%90%E5%9B%B3/%E6%A7%8B%E6%88%90%E5%9B%B3.png">

# 環境設定

## 1. 環境変数の作成

- `docker/local/.env.example`を参考にして`docker/local/.env`を作成
- `project/.env.example`を参考にして`project/.env`を作成

## 2. MT5 の設定を行う

- `docs/MT5で行う設定`を参考にして MT5 上で設定

## 3. Docker 環境の作成

- `make init`コマンドを実行する

## 4. プログラムの実行

- 移動平均線の検知参照

# 移動平均線の検知

## 概要

移動平均線は

- 短期移動平均線: 5日
- 中期移動平均線: 20日
- 長期移動平均線: 60日

と定義しています。

ゴールデンクロス、デッドクロスは短期移動平均線が長期移動平均線を横切った時と定義しています


## 実行方法

以下のコマンドを実行

```
docker compose -f "./docker/local/docker-compose.yml" -p mt5 exec mt5 \
  pipenv run python scripts/moving_average_detection.py --target ZECUSD,M5,30.0,30.0
```

target オプションの指定方法は`銘柄,足,暴騰検知用の数値,暴落検知用の数値`となります

例)

- ZECUSD の 5 分足、15 分足、30 分足、1 時間足
- GOLD の 5 分足、15 分足、30 分足、1 時間足

```
docker compose -f "./docker/local/docker-compose.yml" -p mt5 exec mt5 \
pipenv run python scripts/moving_average_detection.py \
--target ZECUSD,M5,30.0,30.0 \
--target ZECUSD,M15,30.0,30.0 \
--target ZECUSD,M30,30.0,30.0 \
--target ZECUSD,H1,30.0,30.0 \
--target GOLD,M5,30.0,30.0 \
--target GOLD,M15,30.0,30.0 \
--target GOLD,M30,30.0,30.0 \
--target GOLD,H1,30.0,30.0
```

# 概要

株取引である MT5 を監視してゴールデンクロス、デッドクロスなどを検知して slack line グループへ通知を出すプログラムを作りました

ゴールデンクロス、デッドクロスが発生すると流れが大きく変わることが多いため検知できると有利だと考えたためです

あとは面白そうだったからです！

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

<img src="https://github.com/campbel2525/sample-mt5/blob/main/docs/%E6%A7%8B%E6%88%90%E5%9B%B3/%E6%A7%8B%E6%88%90%E5%9B%B3.png?raw=true">

# 環境設定

## 1. 環境変数の作成

- `docker/local/.env.example`を参考にして`docker/local/.env`を作成
- `project/.env.example`を参考にして`project/.env`を作成
  - slack へ通知を出す場合は`SLACK_WEB_HOOK_URL_MOVING_AVERAGE_NOTIFICATION`
  - LINE の特定のグループへ通知を出す場合は`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_MOVING_AVERAGE_NOTIFICATION_GROUP_ID`
    - LINE の設定方法参照

## 2. MT5 の設定を行う

- `docs/MT5で行う設定`を参考にして MT5 上で設定

## 3. Docker 環境の作成

- `make init`コマンドを実行する

## 4. プログラムの実行

- 移動平均線の検知参照

# LINE の設定方法参照

まず以下ことを行てください。詳しい方法はネットで出てきます

1. LINE Developers に登録する
2. Messaging API を有効化
3. Messaging API のアクセストークンを発行
4. グループ作成の許可
5. 自分のスマホの LINE でグループの作成
6. グループ ID の取得の方法を参考にして上記で作った lINE のグループ ID を取得

## グループ ID の取得の方法

サーバー立てずに使える代表格。ログインなしでも OK。

### 手順

1. ブラウザで `https://webhook.site/` を開く

   → いきなり画面上に **ランダムな URL** が出てる（これが受信 URL）

2. その URL をコピーして、LINE Developers の

   **「Messaging API 設定 → Webhook URL」** に貼り付ける

   - 「Webhook の利用」を **オン**
   - 「検証」ボタンを押して、成功になるのを確認

3. 通知に使いたい LINE グループに Bot を招待
4. そのグループで誰かが何か発言する（「test」でも何でもいい）
5. 再び webhook.site の画面を見ると、左側のリクエスト一覧に 1 件増えてるのでクリック

   → 右側の JSON の中にこんなのが出てるはず：

   ```json
   {
     "events": [
       {
         "type": "message",
         "source": {
           "type": "group",
           "groupId": "Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
         },
         "message": {
           "type": "text",
           "text": "test"
         }
       }
     ]
   }
   ```

   この `groupId` が **本物のグループ ID**。

   これを今の `send_line_group_message()` の `group_id` に入れれば OK。

6. groupId をメモしたら、Webhook.site 側のログは削除してもいいし、

   LINE Developers 側の Webhook URL を空に戻しても OK

   （これ以降は push 送るだけなら Webhook 必須じゃない）

# 移動平均線の検知

## 概要

移動平均線は

- 短期移動平均線: 5 日
- 中期移動平均線: 20 日
- 長期移動平均線: 60 日

と定義しています。

ゴールデンクロス、デッドクロスは**短期**移動平均線が**長期**移動平均線を横切った時と定義しています

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

**注意**
現状は LINE への通知は 1 時間足の検出が発生した場合とします。月の送信回数が決まているためなるべく大きい時間足として送信回数を減らしています

実際 5 分足のゴールデンクロス(デッドクロス)はあまり意味ないですし

そのため LINE へ通知をする場合は`--target GOLD,H1,30.0,30.0`のように 1 時間足を含めてください

この辺を変えたい場合は`project/scripts/moving_average_detection.py`の`detect_and_notify_once関数`の`and "1時間足" in message`あたりを修正してください

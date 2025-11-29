## MT5 上でのセットアップ

初回セットアップ（MT5 側）

<!-- ## 0) 事前に用意しておくもの

EA コード（WSL2_FileBridge.mq5）
※ まだファイルが無い場合は、後の手順で「新規作成 → 貼り付け」します。

## 1) データフォルダの場所を開く（あとで Docker で使うパス確認）

MT5 メニュー → 「ファイル」→「データフォルダを開く」

開いたエクスプローラで MQL5 フォルダが見えるはず。

後で使う共有フォルダは
`C:\Users\<Windows ユーザー>\AppData\Roaming\MetaQuotes\Terminal\Common\Files`

（エクスプローラで一度辿って場所を覚えておく） -->

## 2) EA ファイルを置く（または新規作成）

WSL 上のパスで`/mnt/c/Users/<user名>/AppData/Roaming/MetaQuotes/Terminal/<id>/MQL5/Experts/WSL2_FileBridge.mq5`
に`docs/MT5で行う設定/WSL_FileBridge.mq5`をコピペする

Docker 上ではなく WSL 上なことに注意

修正方法参考

```
vi /mnt/c/Users/<user名>/AppData/Roaming/MetaQuotes/Terminal/<id>/MQL5/Experts/WSL2_FileBridge.mq5
```

で保存する。`<user名>`、`<id>`は自分の環境に置き換えること

## 3) コンパイルする

コンパイル方法

MT5 > ツール > MetaEditor > ビルド > コンパイル

画面下の「エラー」タブが 0 件になれば OK。MQL5\Experts\ に WSL2_FileBridge.ex5 が生成されます。

修正する場合は WSL2_FileBridge.mq5 を開いて修正すればいいです。

もしくは直接のパスから修正してもいいです

wsl 上でのパス

`/mnt/c/Users/<user名>/AppData/Roaming/MetaQuotes/Terminal/<id>/MQL5/Experts/WSL2_FileBridge.mq5`

その後はコンパイルを行うこと

## 4) チャートに EA をアタッチ（載せる）

MT5 に戻る → MT5 の上のメニューで [表示] → [ナビゲータ] をクリック -> エキスパートアドバイザ

WSL2_FileBridge を、任意のチャートにドラッグ＆ドロップ。

プロパティで以下を確認：

「アルゴリズム取引を許可」✅（必須）

誤発注を絶対避けたいなら「ライブ取引を許可」は OFF（取得専用運用）。

ツールバーの 「Algo Trading（緑の再生ボタン）」を ON。

~~チャート右上の顔アイコンが笑顔になれば稼働中。<- こんなものはない~~

画面下「エキスパート」タブに

WSL2_FileBridge EA started. ...\Common\Files\ のログが出れば成功。

## 5) 取得したい銘柄を気配値に出す

上メニュー [表示] → [気配値表示]（ショートカット Ctrl+M）

表示された気配置の下にマウスを当てて右クリック -> すべて表示

# Tips

## 1. 銘柄追加

基本は何もしなくて OK。

WSL_FileBridge を 1 つだけどこかのチャートにアタッチしてあれば、命令で指定した銘柄は何個でも取得できます（M5/M15/M30/H1/H4/D1 もそのまま）。

## 2. 気配置に出す

上メニュー [表示] → [気配値表示]（ショートカット Ctrl+M）

表示された気配置の下にマウスを当てて右クリック -> すべて表示

# メモ

https://chatgpt.com/c/690ee517-3534-8322-9b62-682ae81e1e31

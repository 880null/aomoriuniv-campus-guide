# システム構成

```text
ブラウザ (frontend/)
  → 同一オリジン Fetch /api/*
  → Flask (backend/app.py)
  → LedController (backend/controller.py)
  → pySerial / USB
  → Uno R3 (firmware/CampusGuide/src/main.cpp)
  → 抵抗 + LED
```

backend/catalog.py がJSONを検証し、施設と確認済み教室を検索する。
Arduino IDEはfirmware/CampusGuide/CampusGuide.inoを入口としてsrc/main.cppをビルドする。
PlatformIOも同じsrc/main.cppをビルドする。Arduino IDE用の実装を別にコピーしない。
LedController がモード・接続・応答確認済みLED状態を一元管理する。
実機の起動接続に失敗してもHTTPサーバーは稼働する。
scripts/run.py は接続を試行し、Waitressで127.0.0.1:5050にFlaskアプリを配信する。
サーバーの応答確認後にブラウザを開く。Ctrl+Cで停止し、全消灯を試みる。

## 通信契約 v1
- 9600bps / 8bit / parityなし / stop 1bit。
- ASCII、行末LF。ArduinoはCRLFも受理する。
- 起動通知: `READY:CAMPUS:1\n`（全消灯後）。接続時にこの識別子を必須とする。
- Python→Uno: `A\n` / `B\n` / `C\n` / `D\n` / `E\n` / `F\n` / `H\n` / `0\n`。
- Uno→Python: `OK:A\n` など、消灯は `OK:0\n`。点灯変更後に応答する。
- 状態確認: `?\n` → `STATE:A\n` 等、消灯状態は `STATE:0\n`。
- 不正入力: `ERR:INVALID\n`。不正入力では点灯状態を変更しない。
- 受信バッファは固定長。複数文字のコマンドや長すぎる行は行全体を破棄する。
- 正常コマンド/状態確認から10秒経過するとUnoが全消灯する。
- 画面は約2秒間隔で状態確認する。画面を閉じるとハートビートが止まり、最大10秒後に消灯する。

Pythonはポートオープンから最大4秒で起動通知を待ち、その後0のACKを確認する。
通知が読み取りタイムアウトを跨いで分割されても1行に復元する。64バイトを超える行はLFまで破棄する。
各応答の待ち時間は1秒。ポートオープンによるUno自動リセットを前提とする。
自動リセットしない機器では接続試行中にRESETが必要になる場合がある。
ACK不一致・タイムアウト・切断時はポートを閉じ、LED状態を「不明」にする。
状態照会で最後のACKと異なる値を得た場合は現在値に同期し、外部変更を通知する。
実機モードからシミュレーションへ移る際、接続中なら0のACK確認後にポートを閉じる。
未接続から切り替える場合、物理LEDの消灯を確認できない旨を表示する。

## USBポート
公式UnoのVID/PID、またはUnoを明示する名称のポートが1つなら自動選択する。
複数候補や互換機の場合は画面でポートを指定する。関係のない機器へ総当たりで送信しない。
`--serial-port` / `CAMPUS_SERIAL_PORT`でも明示指定できる。
接続状態は最後の通信結果。定期照会で切断を検出する（即時検出ではない）。
再接続時に古い接続の消灯確認が失敗しても、新しい接続の試行へ進む。
新しい接続先では起動通知と消灯ACKを必ず確認し、以前の接続の消灯が未確認だったことを通知する。

## HTTP API
全レスポンスはJSON。失敗時は`error`を返す。制御APIは最新の`status`も返す。

| メソッド/パス | 入力 | 用途 |
| --- | --- | --- |
| GET /api/buildings | q（任意） | 施設一覧/教室検索。buildings, messageを返す |
| GET /api/map | なし | 地図出典/マーカー情報 |
| GET /api/status | なし | 接続/モード/点灯状態照会 |
| GET /api/ports | なし | 選択可能なUSBポート |
| POST /api/select | building_id | 選択して点灯 |
| POST /api/off | {} | 全消灯 |
| POST /api/connection | port（任意） | 再接続 |
| POST /api/mode | mode: real / simulation | モード切替 |

不正入力は400、未知の施設は404、通信失敗は503。
制御POSTはapplication/jsonのみ。別オリジンからの変更は拒否し、Hostはlocalhost/127.0.0.1に制限する。
通信操作は同一ロック内で送信から応答まで行い、複数リクエストの混線を防ぐ。
この制限はローカル展示を想定する。ネットワーク公開は別設計が必要。

## データ
- buildings.json: 施設ID、名前、検索用別名、ピン。教室配置を含めない。
- rooms.json: `rooms`配列。各行にnumber, building_id, source, verified_on (YYYY-MM-DD)。確認済みだけ。
- map.json: 公式画像出典、元画像のサイズ、画像左上を原点とする百分率マーカー座標。

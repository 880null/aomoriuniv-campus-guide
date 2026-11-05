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

## 通信契約 v4（D2〜D6の5施設）
- 9600bps / 8bit / parityなし / stop 1bit。
- ASCII、行末LF。ArduinoはCRLFも受理する。
- 起動通知: `READY:CAMPUS:4\n`（全消灯後）。接続時にこの識別子を必須とする。旧配線のv1/v2/v3は受理しない。
- Python→Uno: `A\n` / `B\n` / `D\n` / `E\n` / `F\n` / `0\n`。
- ピン対応: A=D2、B=D3、D=D4、E=D5、F=D6。C・HはLED未実装のため送信しない。
- Uno→Python: `OK:A\n` など、消灯は `OK:0\n`。点灯変更後に応答する。
- 状態確認: `?\n` → `STATE:A\n` 等、消灯状態は `STATE:0\n`。
- 不正入力（C・Hを含む）: `ERR:INVALID\n`。不正入力では点灯状態を変更しない。
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
| GET /api/buildings | q（任意） | 関連建物、message、番号付き室数、全地点数を返す |
| GET /api/rooms | q, building_id, floor（任意） | 教室・施設の検索／階別一覧（rooms, total）。省略時は全地点 |
| GET /api/rooms/<id> | なし | 1地点の詳細、対応建物（棟不明ならnull） |
| GET /api/map | なし | 地図出典/マーカー情報 |
| GET /api/status | なし | 接続/モード/点灯状態照会 |
| GET /api/ports | なし | 選択可能なUSBポート |
| POST /api/select | building_id | 選択して点灯 |
| POST /api/off | {} | 全消灯 |
| POST /api/connection | port（任意） | 再接続 |
| POST /api/mode | mode: real / simulation | モード切替 |

不正入力は400、未知の施設は404、通信失敗は503。
実機モードでLED未実装のC・Hを選ぶと400を返し、USBへは送信しない。シミュレーションは従来の7施設を利用できる。追加した画面案内のみの施設は両モードで点灯APIを400で拒否する。
画面でLEDのない施設・棟不明地点を選ぶと、情報を表示し、以前の点灯がある場合だけ/api/offで消灯する。通信が失敗しても選択した地点の案内情報は維持し、LED状態とエラーを別に表示する。
制御POSTはapplication/jsonのみ。別オリジンからの変更は拒否し、Hostはlocalhost/127.0.0.1に制限する。
通信操作は同一ロック内で送信から応答まで行い、複数リクエストの混線を防ぐ。
この制限はローカル展示を想定する。ネットワーク公開は別設計が必要。

## データ
- buildings.json: 施設ID、名前、検索用別名、ピン。LED未実装などで未設定のピンはnull。led_noteは未実装・仮設定の表示用。教室配置を含めない。
- extraction/A〜K.json: 全原図の目視転記。source_id、reviewed_pages、ページ／棟／階ごとのgroups。各entryの名前・番号・別名・位置補足。
- rooms.json: 生成済みrooms配列とページ別coverage。id、name、number（null可）、building_id（null可）、floor（null可）、area、位置補足、source_id、source URL、source_page、verified_on、local_plan。
- floorplan_sources.json: 原図11点のURL、未加工コピーのパス、取得日、ページ数、SHA-256。詳細はROOM_DATA.md。
- 番号付き室の索引と全案内地点の索引を分ける。番号だけの検索は完全一致し、名前は別名・建物・階と組み合わせて検索する。階を番号から計算しない。
- 追加施設のIDはPIN_MAPへ追加しない。物理出力は配線設定済み5ピンのまま。
- map.json: 公式画像出典、元画像のサイズ、画像左上を原点とする百分率マーカー座標。

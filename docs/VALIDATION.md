# 実装と検証記録

現行の確認済み配線は1号館=D2、3号館=D3、5号館=D4、6号館=D5、7号館=D6。4号館とレストラン棟は確認待ち。
以下には旧配線で行った検証の履歴も含む。最新の結果は「実装担当者の配線に更新」の節を参照。

## 段階ごとの変更

| 段階 | 主なファイル | 実装内容 | 確認方法・結果 |
| --- | --- | --- | --- |
| 1. 構成設計 | backend/, frontend/, firmware/, data/, scripts/, tests/ | Web・通信・ハードウェアを分離 | 空のワークスペースから作成。構成をREADMEに記載 |
| 2. 開発指示・仕様 | AGENTS.md、docs/PROJECT_CONTEXT.md、REQUIREMENTS.md、ARCHITECTURE.md、HARDWARE.md | 背景、対象施設、API、通信、配線 | 開発依頼の7施設・ピン・対象外施設と照合 |
| 3. バックエンド | backend/app.py、catalog.py | Flask API、検索、JSON検証 | unittest / 実HTTPの起動・検索確認 |
| 4. 基本画面 | frontend/index.html、static/style.css | 検索・施設一覧・地図・接続設定 | Chromeで画面と地図画像を表示、スクリーンショットを目視確認 |
| 5. 7施設選択 | static/app.js、data/buildings.json、map.json | 一覧と地図の連動、選択情報、状態不明の区別 | APIテストで全7施設。Chromeでマーカー位置、選択状態、不明表示を確認 |
| 6. Arduino | firmware/platformio.ini、src/main.cpp | 7出力、入力検証、起動通知、10秒監視 | Uno用PlatformIOビルド成功。実コードのC++スタブテスト成功 |
| 7. USB通信 | backend/controller.py | ポート選択、起動通知、ACK、状態照会、排他制御 | 模擬ポートでACK不一致・切断・タイムアウト・同時操作を確認 |
| 8. シミュレーション | controller.py、app.js | USB送信なしの点灯状態、明示的モード表示 | API/HTTPで7施設選択・消灯。USBファクトリーが呼ばれないことをテスト |
| 9. 起動 | start.command、start.bat、scripts/bootstrap.py、run.py | venv、依存確認、Waitress、準備完了後ブラウザ起動 | Macスクリプトからサーバー起動を確認。実HTTPと正常終了確認 |
| 10. テスト・文書 | tests/、README.md、.gitignore、.vscode/ | 41テスト、セットアップ手順、開発タスク | 全41件成功、JS/zsh構文確認、依存整合性、Git除外確認 |

## 初回実装の自動確認の結果

環境: macOS / Python 3.15.2。導入された主要依存関係: Flask 3.1.3、pySerial 3.5、Waitress 3.0.2。

```text
python -W error::ResourceWarning -m unittest discover -s tests -v
Ran 41 tests ... OK

node --check frontend/static/app.js
成功

zsh -n start.command
成功

python -m pip check
No broken requirements found.
```

PlatformIO Core 6.2.0 / atmelavr 5.1.0 / Arduino AVR Framework 5.2.0:

```text
pio run -d firmware
[SUCCESS]
RAM:   210 / 2048 bytes (10.3%)
Flash: 2458 / 32256 bytes (7.6%)
```

PlatformIOの確認用環境は一時ディレクトリに導入。アプリ本体のrequirementsには追加していない。

実HTTPの確認には専用ポート5051と存在しないUSBポート指定を使用し、実機への接続・送信を行わなかった。

```text
未接続の実機モードでHTTP起動 → 状態unknown
HTML / ローカルPNG画像 → 200
シミュレーションへ切替 → 全消灯
A/B/C/D/E/F/Hを順に選択 → 対応するactive_building
全消灯 → off
未登録教室101 → 検索結果なし
Ctrl+C相当で終了 → exit 0
```

ローカルGit初期化済み。`.venv/`、`firmware/.pio/`、Pythonキャッシュの除外を確認。
初回実装の検証時点ではGitHubリモートの設定・コミット・pushは未実施。
後続のGitHub接続作業で、非公開リポジトリ [880null/aomoriuniv-campus-guide](https://github.com/880null/aomoriuniv-campus-guide) を作成し、ソースの保存先とした。実機の検証状況は変わらない。

## 2026-11-01: 実機がない環境での追加検証

### 方法

`tests/firmware/serial_bridge.cpp`が実際の`firmware/CampusGuide/src/main.cpp`を読み込み、別プロセスで実行する。
アプリ側はシミュレーションモードではなく、実機モードの`LedController`とpySerial本体を使う。
macOSの仮想シリアルポートを通し、実際のコマンドとCRLF応答を送受信する。
検査用の別経路でD2〜D8の模擬出力値を取得し、APIが成功しただけでなくピンの対応も照合する。
USBのDTRリセットだけは別経路のRESET操作で再現する。

Arduino AVR Frameworkの`Print.cpp`と`HardwareSerial.h`を読み、`println()`のCRLFと`Serial.begin(9600)`の標準8N1設定も確認した。
検証用Serialの改行を実装と同じCRLFに揃えた。

### 結合テスト10件の結果

| 確認内容 | 結果 |
| --- | --- |
| 接続時の起動通知・全7出力の消灯 | 成功 |
| A/B/C/D/E/F/HとD2/D3/D4/D5/D6/D7/D8の対応、0で全消灯 | 成功 |
| 最後の有効通信から10秒経過後の自動消灯、APIへの反映 | 成功 |
| 状態照会による自動消灯の延期（8秒間隔で5回） | 成功 |
| 不正コマンド・1000文字の長い行・分割コマンド・CRLF | 成功 |
| 通信切断でLED状態不明、再接続後の操作復帰 | 成功 |
| 切断検知前でも1回の再接続操作で復帰 | 成功 |
| ファームウェアの予期しないリセットを検知し再接続 | 成功 |
| シミュレーションへの切替と正常終了で模擬ピンを消灯 | 成功 |
| 140回の連続選択でACKと出力の整合性を維持 | 成功 |

自動消灯の結合テストは検査用の時計を進めて実施した。実物のクロック精度は検証していない。
既存C++論理テストには、出力モード設定とunsigned longの桁あふれを跨ぐタイマー判定も追加した。
ホスト上のC++実行であり、AVR命令や32bitタイマーそのもののエミュレーションではない。

### 見つけた問題と修正

- 分割された起動通知を読み取りごとに捨ててしまい、4秒以内に全文が届いても接続できなかった。改行まで部分行を保持するよう修正した。
- 64バイトを超える起動時ノイズの途中に識別子があると、行の途中から起動通知と認識できてしまった。長い行は改行まで破棄するよう修正した。
- 古い接続の消灯に失敗すると、新しい接続の試行前に処理が終わっていた。消灯未確認を記録しつつ、新しい接続を初期化するよう修正した。

いずれも修正前の失敗をテストで再現し、修正後の成功を確認した。
不正な長い行の後でも、次の正常な起動通知で接続できることも確認した。

```text
python -W error::ResourceWarning -m unittest discover -s tests -v
Ran 55 tests ... OK（スキップなし）

pio run -d firmware
[SUCCESS]
RAM: 210 / 2048 bytes
Flash: 2458 / 32256 bytes
```

### この検証で確定できないこと

USB機器としての実際の認識、DTRによる自動リセットと起動時間、ATmega328P上の実行、電圧・電流、配線、LEDの極性・故障は未確認。
これらは実物を接続して最終確認する必要がある。ソフトウェアの結合テスト成功を、実機での点灯確認済みとは扱わない。

## 2026-11-01: Arduino IDE形式への対応

- Arduino IDE 2で開く`firmware/CampusGuide/CampusGuide.ino`を追加。
- 実装を`firmware/CampusGuide/src/main.cpp`へ移し、PlatformIOとArduino IDEで共用。制御ロジックと通信仕様の変更なし。
- GitHub ZIPの展開から初回書き込み、PC側起動ファイル実行までの手順をREADMEとHARDWAREに追加。
- Arduino CLI 1.5.1 / 公式Arduino AVR Boards 1.8.8 / `arduino:avr:uno`でスケッチのコンパイル成功。
- PlatformIOの既存ビルドと、55件の自動テストも成功。
- Arduino CLIとPlatformIOが生成したHEXファイルがバイト単位で一致することを確認。SHA-256: `cf3f86422cccb9d79f46f91957fbbe908d5458b227ff8442fc70eb9a36b904cf`。

```sh
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:uno firmware/CampusGuide
```

```text
Sketch uses 2458 bytes of program storage space.
Global variables use 210 bytes of dynamic memory.
```

検証ツールとボード定義は一時ディレクトリへ導入した。`--warnings all`では公式AVRコアのnew.cppに未使用引数の警告が4件出るが、プロジェクト側のコンパイル警告・エラーはなかった。
Arduino IDEのGUI操作と基板への実際の書き込みは未確認。Arduino CLIによるコンパイル確認と区別する。
Arduino IDEの導入はPC側のPython環境やUSBドライバーの準備を代替しない。Windowsでの実行確認は引き続き必要。

## 実装担当者の配線に更新

ユーザーを通して共有された「5=6号館、3=3号館、4=5号館、6=7号館、2=1号館」をデジタルピン番号として反映。

| 記号 | 施設 | 現在のピン |
| --- | --- | --- |
| A | 1号館 | D2 |
| B | 3号館 | D3 |
| D | 5号館 | D4 |
| E | 6号館 | D5 |
| F | 7号館 | D6 |
| C | 4号館 | 未確認・実機点灯は保留 |
| H | レストラン棟 | 未確認・実機点灯は保留 |

- JSON、バックエンド、Arduinoファームウェア、画面の表示、仕様書を更新。
- 実機では未確認のC/Hを送信せず、Arduinoへ直接送られた場合も拒否する。既に点灯中の別施設を誤って変更しないことを確認。
- シミュレーションは施設7件を維持し、C/Hも画面上で確認できる。
- 起動識別子を`READY:CAMPUS:2`へ更新。旧配線v1のスケッチを誤って使わないよう、接続を拒否するテストを追加。更新後はスケッチの再書き込みが必要。
- 仮想ポート結合テストでA/B/D/E/FがD2/D3/D4/D5/D6に対応することを確認。140回の連続選択、切断復帰、全消灯、監視タイマーも成功。

```text
Ran 58 tests ... OK（スキップなし）
node --check frontend/static/app.js: 成功
PlatformIO Unoビルド: SUCCESS
Arduino CLI / arduino:avr:uno: 成功
RAM: 206 / 2048 bytes
Flash: 2448 / 32256 bytes
```

両ビルドのHEXは一致。SHA-256: `2b150594ba533b847ee000367974ad15b56ab800be138b1a0b7bd3d800c36f7d`。
実物への書き込み・点灯確認は未実施。画面変更はJavaScript構文とAPIの確認を行い、GUIの全操作確認は未実施。

## 検証の限界と残る受入確認

- **実機の書き込み・点灯・配線は未確認**。C++スタブとAVRコンパイルの成功は実機検証を意味しない。
- 実Unoで起動通知、確認済み5ピン、未確認施設の命令拒否、消灯、USB抜去/再接続、10秒自動消灯を確認する。
- Windowsのstart.batは作成済み。Windows実行環境での起動は未確認。
- Macのstart.commandはターミナルから実行確認。Finderのダブルクリック起動と自動ブラウザ起動の一連動作は未確認。
- Chromeで画面・地図・選択・未接続表示を確認。ブラウザ制御ツールが不安定だったため、検索入力・モード切替・7施設すべてのクリック操作の連続確認は完了していない。これらのAPI動作は自動確認済み。
- スマートフォン、他ブラウザ、スクリーンリーダーの実操作は未確認。
- 実教室の対応は資料未提供のため0件。登録後の現地照合が必要。

実機確認にはdocs/HARDWARE.mdのチェックリストを使う。

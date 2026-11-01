# 青森大学 インタラクティブキャンパスガイド

青森大学「プログラミングワークショップⅡ」で制作する、WebとArduino Uno R3を連携したキャンパス案内です。建物名・確認済みの教室番号から施設を探し、公式マップと実物模型のLEDで案内します。

## できること
- 7施設の一覧・建物名検索・地図からの選択
- 選択した建物とLED状態の表示、全消灯
- Arduinoの接続状態と通信エラーの表示、USBポートの選択・再接続
- 実機と明確に区別したシミュレーション
- Mac / Windowsの起動スクリプトとブラウザの自動表示

**教室配置の正式データは未提供のため0件です。** 教室検索の仕組みはありますが、未登録番号を建物番号から推測しません。建物名または地図から選んでください。

## 必要な環境
- Python 3.10以上（WindowsではPython LauncherまたはPATH設定が必要）
- Chrome、Edge、Safari等の現在のブラウザ
- 初回セットアップ時のインターネット接続
- 実機利用時: Arduino Uno R3、データ通信対応USBケーブル、確認済み5施設分の配線済みLED
- 初回書き込み時: Arduino IDE 2（またはVS CodeのPlatformIO IDE拡張 / PlatformIO CLI）

通常起動にはNode.jsやPlatformIOは不要です。初回にPython依存関係を入れたあとは、地図を含めオフラインで動きます。

## GitHubからダウンロードして使う

1. [GitHubリポジトリ](https://github.com/880null/aomoriuniv-campus-guide)にログインし、「Code → Download ZIP」で取得して展開します。Gitのインストールは不要です。
2. PCにPython 3.10以上を用意します。初回の基板書き込み用にArduino IDE 2も用意します。
3. `firmware/CampusGuide/CampusGuide.ino`をArduino IDEで開き、ボード「Arduino Uno」とUSBポートを選んで「書き込み」を押します。
4. Arduino IDEのシリアルモニターを閉じます。
5. 展開したプロジェクト直下の、Windowsなら`start.bat`、Macなら`start.command`を開きます。Webアプリが起動します。

`CampusGuide`フォルダー内の`src/main.cpp`も必要なので、`.ino`だけを取り出さないでください。
Arduino IDEが起動するのは基板側のプログラムです。PC側のPython/Webアプリは起動ファイルで別に実行します。
書き込みは初回または基板のプログラム更新時だけ必要です。日常の利用ではUSB接続とPC側の起動ファイルだけで使えます。
Arduino IDE経由でも、PC側のPython環境・USB認識・ポート選択の確認は必要です。Windows/Macそれぞれでの実行や基板への書き込みの確認状況は、[検証記録](docs/VALIDATION.md)を参照してください。

## 起動

### Mac
`start.command`をダブルクリックします。ターミナルからも起動できます。

```sh
./start.command
```

実行権限がない場合だけ、プロジェクト内で`chmod +x start.command`を実行してください。

### Windows
`start.bat`をダブルクリックします。

### Arduinoがない場合
通常起動後、画面下の「接続・動作モードの設定」から「シミュレーション」を選べます。最初からシミュレーションで起動することもできます。

```sh
# Mac
./start.command --simulate
```

```bat
rem Windows（コマンドプロンプト）
start.bat --simulate
```

仮想環境`.venv/`を作成して依存関係を確認し、http://127.0.0.1:5050 を自動表示します。Arduinoが見つからなくてもWebアプリは起動します。通常起動は実機モードで、未接続からシミュレーションへ自動的に切り替わることはありません。

起動したターミナルを開いたまま使い、終了時は**Ctrl+C**を押してください。接続中なら全消灯を試みます。ターミナルの強制終了や切断では消灯確認できませんが、ファームウェアは通信が10秒途絶えると全消灯します。

### 起動オプション
Macの`./start.command`、Windowsの`start.bat`の後ろに指定します。

| オプション | 意味 |
| --- | --- |
| `--simulate` | USBを使わないシミュレーション |
| `--no-browser` | ブラウザの自動起動を省略 |
| `--serial-port COM3` | USBポートを明示指定。Macは`/dev/cu.usbmodem...`等 |
| `--port 5051` | HTTPポートを変更 |

ポートは画面でも選べます。Uno候補が複数、または互換ボードの場合は手動指定してください。環境変数`CAMPUS_SERIAL_PORT`も利用できます。

### 手動セットアップ
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.run --simulate
```

Windowsでは`python3`を`py -3`、`.venv/bin/python`を`.venv\Scripts\python.exe`に読み替えてください。VS Codeの「タスクの実行」には実機/シミュレーションの2タスクを用意しています。

## Arduinoの初回準備

| コマンド/地図記号 | 建物 | ピン |
| --- | --- | --- |
| A | 1号館 | D2 |
| B | 3号館 | D3 |
| C | 4号館 | 未確認（実機点灯は保留） |
| D | 5号館 | D4 |
| E | 6号館 | D5 |
| F | 7号館 | D6 |
| H | レストラン棟 | 未確認（実機点灯は保留） |
| 0 | 全消灯 | — |

実装担当者から共有されたピン対応を反映しています。実機LEDは1・3・5・6・7号館の5施設が対象です。
4号館とレストラン棟はピンの確認待ちで、実機へ点灯命令を送りません。施設情報とシミュレーションは7施設のまま利用できます。
旧スケッチとは配線が異なるため、今回の更新時はArduinoへスケッチを再度書き込んでください。

各ピン→220〜330Ω抵抗→LED→GNDと配線します。LEDごとに抵抗が必要です。詳細は[配線と書き込み](docs/HARDWARE.md)を参照してください。

Arduino IDE 2で`firmware/CampusGuide/CampusGuide.ino`を開き、ボードとポートを選んで「書き込み」を押します。ボード定義が未導入の場合は「Arduino AVR Boards」を導入します。

PlatformIOを使う場合:

```sh
cd firmware
pio run
pio run --target upload
```

VS Codeでは`firmware/`をPlatformIOで開いてBuild→Uploadでも書き込めます。初回の書き込み以後は、電源投入時に自動実行されます。アプリの使用前にシリアルモニターを閉じてください。

通信は9600bps、ASCII、LF区切りです。`A\n`に`OK:A\n`、`0\n`に`OK:0\n`が返ります。接続には`READY:CAMPUS:2`の起動通知が必要です。古い配線のv1スケッチは接続を拒否します。詳しくは[通信設計](docs/ARCHITECTURE.md)を参照してください。

## データの追加

- `data/buildings.json`: 施設7件とピン、検索用の別名。配線未確認の施設のpinはnull
- `data/rooms.json`: **確認済み**教室だけ
- `data/map.json`: 地図画像の出典とマーカー座標（左上からの百分率）

教室を追加するときは、大学の資料または担当者の確認で対応を確定してから、`rooms`配列へ次の形式で記載します。以下は項目の説明であり、正式データにそのままコピーしないでください。

```text
number: 教室番号（文字列）
building_id: A/B/C/D/E/F/Hのいずれか
source: 確認した大学資料・担当者等の情報
verified_on: 実際の確認日（YYYY-MM-DD）
```

重複番号、確認元の欠落、対象外の建物、未来の確認日は起動時に拒否します。変更後はアプリを再起動してください。全角英数字と空白は検索時に正規化します。

地図は[青森大学公式アクセスページ](https://www.aomori-u.ac.jp/access/)の画像を保存して使用しています。出典、取得日、権利の扱いは[企画経緯](docs/PROJECT_CONTEXT.md)に記録しています。地図画像を差し替えた場合は全マーカーの座標を見直してください。

## プロジェクト構成

```text
AGENTS.md                  Codex向け開発指示
README.md / requirements.txt
docs/
  PROJECT_CONTEXT.md       企画経緯・地図出典
  REQUIREMENTS.md          要件と受入確認
  ARCHITECTURE.md          通信契約・API・モジュール
  HARDWARE.md              配線・書き込み・実機チェック
backend/
  app.py                   Flask APIと画面配信
  catalog.py               JSON検証と検索
  controller.py            USB通信・ACK・モード管理
frontend/
  index.html
  static/                  JavaScript・CSS・公式地図
firmware/
  platformio.ini
  CampusGuide/
    CampusGuide.ino        Arduino IDEで開くファイル
    src/main.cpp           両方の開発環境で共通のUnoプログラム
data/                      施設・教室・マーカーJSON
scripts/                   環境準備とサーバー起動
tests/                     API・検索・模擬通信・ファームウェア論理テスト
start.command / start.bat
```

Web Serial APIは使いません。ブラウザ→Fetch→Flask→pySerial→USB→Uno→LEDの順です。WaitressでFlaskアプリをローカルホストだけに配信し、デバッグと自動リロードは無効です。

## テスト

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check frontend/static/app.js
cd firmware
pio run
```

Pythonテストは58件です。ファームウェアの論理テスト1件にはC++コンパイラ（clang++またはg++）が必要です。シリアル結合テスト11件には、さらにmacOS/LinuxのPOSIX仮想ポートが必要です。条件を満たさないテストはスキップします。Node.jsはJavaScriptの構文確認だけに使用します。

結合テストでは`Flask API → 実際のpySerial → OSの仮想シリアルポート → 実際のmain.cpp → 模擬ピン出力`をつなぎ、確認済み5施設の点灯・消灯、未確認施設の命令拒否、連続選択、切断・再接続、通信停止時の自動消灯を確認します。`Serial`・時計・GPIOは検証用の代替実装です。USB回路、UnoのDTR自動リセット、配線、LEDの実際の点灯を保証するものではありません。

結合テストだけを実行する場合:

```sh
.venv/bin/python -m unittest discover -s tests -p test_serial_integration.py -v
```

確認できた範囲と、実機・OSごとの未確認項目は[検証記録](docs/VALIDATION.md)にまとめています。実際のLED、USB切断・再接続、Windowsの起動は、展示用機材で受入確認してください。

## 困ったとき

| 症状 | 確認すること |
| --- | --- |
| Pythonが見つからない | Python 3.10以上、WindowsのPATH/Launcher |
| 初回のパッケージ導入失敗 | ネット接続、組織のプロキシ設定。次回起動で再試行できます |
| 仮想環境を別PCからコピーした | `.venv`はPC間で持ち運ばず、そのPCで作り直す |
| ブラウザが開かない | ターミナル記載のURLを手動で開く |
| ポート5050が使用中 | 二重起動を確認、または`--port 5051` |
| Unoを検出できない | USBケーブル、ポート一覧更新、手動選択、必要なUSBドライバー |
| 起動通知を確認できない | ファームウェア書き込み、9600bps、他のシリアルアプリ終了。自動RESETしないボードでは接続試行中にRESET |
| 応答不一致/タイムアウト | USB・配線を確認して再接続。画面の点灯成功表示は行いません |
| 教室検索が0件 | 未登録番号は案内できません。建物名で検索する |

画面は約2秒ごとに実機状態を照会します。USB抜去直後には前の表示が残る場合があります。次の照会失敗で「状態不明」に変わります。複数タブで開くと点灯状態は全タブで共有され、最後に選択した建物が点灯します。

## Git / GitHub

GitHubの保存先は非公開リポジトリ [880null/aomoriuniv-campus-guide](https://github.com/880null/aomoriuniv-campus-guide) です。`origin`から`main`ブランチを管理します。`.venv/`、Pythonキャッシュ、`.pio/`、秘密情報、OS一時ファイルを除外しています。

変更を保存してGitHubに反映する場合:

```sh
git add .
git commit -m "Describe your changes"
git push
```

公開する場合は、同梱した大学地図画像の利用条件も大学に確認してください。

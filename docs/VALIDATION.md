# 実装と検証記録

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

## 自動確認の結果

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

## 検証の限界と残る受入確認

- **実機の書き込み・点灯・配線は未確認**。C++スタブとAVRコンパイルの成功は実機検証を意味しない。
- 実Unoで起動通知、7ピン、消灯、USB抜去/再接続、10秒自動消灯を確認する。
- Windowsのstart.batは作成済み。Windows実行環境での起動は未確認。
- Macのstart.commandはターミナルから実行確認。Finderのダブルクリック起動と自動ブラウザ起動の一連動作は未確認。
- Chromeで画面・地図・選択・未接続表示を確認。ブラウザ制御ツールが不安定だったため、検索入力・モード切替・7施設すべてのクリック操作の連続確認は完了していない。これらのAPI動作は自動確認済み。
- スマートフォン、他ブラウザ、スクリーンリーダーの実操作は未確認。
- 実教室の対応は資料未提供のため0件。登録後の現地照合が必要。

実機確認にはdocs/HARDWARE.mdのチェックリストを使う。

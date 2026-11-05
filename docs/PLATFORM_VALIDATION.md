# Mac / Windowsの動作検証

確認日: 2026-11-02。実際に実行した環境と、準備しただけの検証を区別する。

2026-11-05に実機対象を5施設・通信v4へ更新した。[v4のGitHub Actions実行41979172438](https://github.com/880null/aomoriuniv-campus-guide/actions/runs/41979172438)で4ジョブすべて成功した。以下の詳細表はv3時点のCI履歴。新しい実機接続と確認限界は[実機検証記録](HARDWARE_VALIDATION_2026-11-05.md)を参照。

## 今回の実行環境と結果

[GitHub Actionsの実行](https://github.com/880null/aomoriuniv-campus-guide/actions/runs/41379844775)で4ジョブすべて成功。対象コミットは`2b88f2ca5c7e0fa4742ca79f30c60d5562e0b50b`。その後の変更は共有用のREADME・手順・検証資料で、アプリの実装は同じ。

| 実行環境 | Python | 起動・HTTP・模擬点灯・未接続・オフライン再起動 | ブラウザ操作 | Unoビルド |
| --- | --- | --- | --- | --- |
| macOS 15.7.9 / Intel x86_64（CI） | 3.10.21 | 成功 | このジョブでは対象外 | このジョブでは対象外 |
| macOS 26.6.2 / ARM64（CI） | 3.13.17 | 成功 | Chromium / WebKit成功 | 成功 |
| Windows Server 2025 / x64（CI） | 3.10.11 | 成功 | このジョブでは対象外 | このジョブでは対象外 |
| Windows Server 2025 / x64（CI） | 3.13.16 | 成功 | Chromium / Microsoft Edge成功 | 成功 |
| macOS 27.2 / Apple Silicon（手元） | 3.15.2 | 成功 | Chromium / WebKit成功 | 成功 |

CIの全ジョブでDOM結合テスト3件が成功。PythonテストはMacで65件成功、Windowsで54件成功・POSIX仮想ポートを使う11件をスキップした。WindowsのC++模擬ファームウェアの論理テストは成功している。UnoビルドはMac・Windowsの両方でRAM 208 / 2048 bytes、Flash 2458 / 32256 bytes。ビルド成功は基板への書き込み・点灯の確認とは区別する。

初回セットアップは、新しい日本語・空白入りフォルダーへコピーし、Macは`start.command`、Windowsは`start.bat`を実行して確認した。Python 3.10でも実際に仮想環境を作成し、依存関係の準備と再起動に成功した。

実行時に保存された結果JSON:

- [Mac Intel / Python 3.10](platform-results/ci-41379844775-macos-intel-py310.json)
- [Mac ARM64 / Python 3.13](platform-results/ci-41379844775-macos-arm64-py313.json)
- [Windows / Python 3.10](platform-results/ci-41379844775-windows-py310.json)
- [Windows / Python 3.13](platform-results/ci-41379844775-windows-py313.json)
- [手元のMac / Python 3.15](platform-results/macos-arm64-2026-11-02.json)

WindowsのPython 3.10の`platform.platform()`は`Windows-10-10.0.26100-SP0`と表示するが、ジョブ開始ログのOS情報は両WindowsジョブともMicrosoft Windows Server 2025 / 10.0.26100 / Datacenter。Windows 10の実機で検査したという意味ではない。

## 確認の限界

- Arduino実機のUSB認識・DTRリセット・書き込み・配線・LED点灯は、両OSとも未確認。
- Finder / Explorerでの起動ファイルのダブルクリックは未確認。コマンド経由でOS用起動ファイルを実行した。
- 既定ブラウザの自動起動は、`--no-browser`で検査したため未確認。
- ブラウザはヘッドレスでの検証。WebKitは市販Safariアプリそのものの手動操作ではない。
- Windows Server上のCIであり、グループ各自のWindows 10 / 11実機、USBドライバー、ウイルス対策や組織の制限は未確認。
- Windowsでは子プロセスを含めた終了を検査し、利用者のCtrl+C操作は未確認。

## 実行する検査

`scripts/verify_runtime.py`がアプリの実装・データと起動ファイルを一時フォルダーへコピーし、次を確認する。利用者の既存`.venv`や起動中の5050番サーバーは変更しない。

1. 「青森 大学 キャンパスガイド」という日本語・空白入りフォルダーから、OS用起動ファイルの`--help`を実行して初回環境を準備する。
2. 同じ起動ファイルで、未使用ポートのシミュレーションサーバーを起動する。
3. HTML・CSS・JavaScript・地図・11点のPDF、14施設、13マーカー、5301教室の建物／階、未登録番号の応答を確認する。
4. シミュレーションの7施設選択・消灯を確認する。
5. ブラウザ指定時は、実際のHTTPサーバーへ接続し、地図・CSSの読込、マーカー選択、全角番号検索、教室詳細、PDFリンク、非LED施設選択時の消灯、階フィルター、未登録番号を操作する。
6. 幅1440pxと390pxで表示し、横方向のはみ出し、JavaScriptの未捕捉エラーを検査してスクリーンショットを保存する。
7. 実機モードに切り替え、Arduino未接続でも教室情報を表示し、LED状態を不明と表示することを確認する。
8. パッケージ取得を禁止した状態で実機モードへ再起動し、未接続でもWeb画面・検索が動くことを確認する。
9. 検証用サーバーだけを終了し、ポートが閉じたことを確認する。

実機への誤接続を避けるため、検証時は存在しないシリアルポートを明示する。MacではプロセスグループへSIGINTを送り、WindowsのCIでは対話コンソールがないため子プロセスを含めて終了する。Windowsの終了処理は、利用者のCtrl+C操作を検証したものではない。

常駐プロセスのログはローカル一時領域へ出力してから結果フォルダーへコピーする。OneDrive内の開いた出力ファイルを子プロセスへ渡す条件では検証プロセスが途中終了するケースがあり、この条件を避けた。通常アプリの処理を変更して失敗を隠すものではない。

## 手元で再現する

HTTPと起動ファイルだけの検証はPython標準ライブラリで実行できる。初回のパッケージ導入にはネット接続が必要。

```sh
python scripts/verify_runtime.py --report validation-results/runtime.json
```

ブラウザ操作も確認する場合は、検証用環境へ`tests/requirements-browser.txt`を導入する。アプリの通常依存関係には含めない。

```sh
python -m pip install -r tests/requirements-browser.txt
python -m playwright install chromium
python scripts/verify_runtime.py --browser chromium --report validation-results/runtime.json
```

Macでは`python -m playwright install webkit`を追加し、`--browser webkit`も指定できる。Windowsではインストール済みのEdgeに対して`--browser msedge`を指定できる。

結果JSON、起動ログ、PNGは`validation-results/`へ保存する（Git管理対象外）。JSONにはOS・CPU・Python・合否・検証限界を残す。失敗時は調査用の一時フォルダーを残し、`debug_workspace`へパスを記録する。

## GitHub Actionsで再現する

[.github/workflows/cross-platform.yml](../.github/workflows/cross-platform.yml)で、次の4ジョブを実行する。

- macOS Intel / Python 3.10
- macOS ARM64 / Python 3.13（Chromium / WebKitとUnoビルドも検査）
- Windows / Python 3.10
- Windows / Python 3.13（Chromium / EdgeとUnoビルドも検査）

各ジョブでPythonテスト、JavaScript構文、公式データの再生成一致、DOM結合テスト、OS用起動ファイルを検証する。WindowsではPOSIX仮想シリアルの11テストは環境要件によりスキップされる。スキップを実機通信の成功とは扱わない。今回のジョブログと成果物（保存期間14日）には画面画像と起動ログも残す。[READMEの画面例](screenshots/campus-guide.png)はWindowsのEdgeで撮影したシミュレーションの画像。

GitHub CLIの追加認証が必要な場合のコマンド:

```sh
gh auth refresh -h github.com -s workflow
```

関連ファイルをコミット・Pushすると自動実行する。必要に応じてActionsの「Cross-platform verification」から手動実行もできる。終了後は各OSのジョブログと`verification-*`成果物を確認する。**ワークフローがあるだけでは検証完了ではない。成功した実行URLと対象コミットを記録して初めて、その環境での成功とする。**

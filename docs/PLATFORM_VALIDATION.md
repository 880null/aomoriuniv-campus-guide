# Mac / Windowsの動作検証

確認日: 2026-11-02。実際に実行した環境と、準備しただけの検証を区別する。

## 今回の実行環境

| 項目 | Mac（手元の実環境） | Windows |
| --- | --- | --- |
| OS / CPU | macOS 27.2 / Apple Silicon ARM64 | このPCに実行環境なし |
| Python | 3.15.2 | CIでは3.10 / 3.13を予定 |
| 起動ファイル | `start.command`をzshから実行 | `start.bat`の検証を準備済み、未実行 |
| 初回セットアップ | 新しい日本語・空白入りフォルダーで仮想環境・依存関係を準備 | 未実行 |
| ブラウザ | 検証用Chromium / WebKitで画面操作に成功 | CIでChromium / Microsoft Edgeを予定 |
| Finder / Explorerのダブルクリック | 未確認 | 未確認 |
| 既定ブラウザの自動起動 | 今回は`--no-browser`のため未確認 | 未確認 |
| Arduino実機のUSB・配線・LED | 未確認 | 未確認 |

Windows検証はGitHub Actionsの実OS上で行う構成を作成したが、現在のGitHub CLI認証に`workflow`スコープがないため、GitHubがワークフローのPushを拒否した。**Windowsで実行成功したとは扱わない。**

今回のMac検証は全項目成功。Python自動テスト65件、DOM結合テスト3件、PlatformIOのUnoビルドも成功（RAM 208 / 2048 bytes、Flash 2458 / 32256 bytes）。[実行結果JSON](platform-results/macos-arm64-2026-11-02.json)を同梱する。ブラウザ操作にはヘッドレスの検証用エンジンを使用しており、市販Safariアプリそのものの手動操作ではない。

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

[docs/testing/cross-platform.yml](testing/cross-platform.yml)に、認証後に有効化するワークフローテンプレートとして次の4ジョブを用意した。現在は実行されない資料ファイルであり、`.github/workflows/`には配置していない。

- macOS Intel / Python 3.10
- macOS ARM64 / Python 3.13（Chromium / WebKitとUnoビルドも検査）
- Windows / Python 3.10
- Windows / Python 3.13（Chromium / EdgeとUnoビルドも検査）

各ジョブでPythonテスト、JavaScript構文、公式データの再生成一致、DOM結合テスト、OS用起動ファイルを検証する。WindowsではPOSIX仮想シリアルの11テストは環境要件によりスキップされる。スキップを実機通信の成功とは扱わない。

GitHub CLIの追加認証が必要な場合のコマンド:

```sh
gh auth refresh -h github.com -s workflow
```

認証後はテンプレートを`.github/workflows/cross-platform.yml`へ移動してコミット・Pushすると自動実行する。必要に応じてActionsの「Cross-platform verification」から手動実行もできる。終了後は各OSのジョブログと`verification-*`成果物を確認する。**ワークフローがあるだけでは検証完了ではない。成功した実行URLと対象コミットを記録して初めて、その環境での成功とする。**

# READMEの構成図

作成日: 2026-11-02。アプリの実装と`docs/ARCHITECTURE.md`に基づく技術・通信の説明図。

- `campus-guide.source.html`: 編集用。stack-diagramのアイコン・フォント置換トークンを含む。
- `campus-guide.html`: アイコンと欧文フォントを埋め込んだ自己完結HTML。図だけを表示する。日本語はPCの日本語フォントを使用する。
- `campus-guide.png` / `campus-guide-dark.png`: 同じHTMLから生成した明暗2種類のPNG。READMEは閲覧環境のテーマで切り替える。
- `icon-sources.json`: 使用したロゴ・ピクトグラムの取得元。
- `licenses/`: テンプレート、フォント、アイコン配布元のライセンス文。

アプリの起動に図の生成ツールは不要。構成図HTMLを開いても、検索画面やUSB接続は起動しない。アプリはプロジェクト直下の`start.command`／`start.bat`を使用する。

## 作成ツールと出典

[caru-ini/stack-diagram](https://github.com/caru-ini/stack-diagram)のテンプレート・アイコン取得・HTML生成・PNG書き出し手順を使用。

使用コミット: `75dbd3e3c6fe28844322e6064d3a947b870a6c61`。
描画: Playwright 1.64.1 / Chromium Headless Shell 156、PNGは2倍解像度。明暗両方の出力を目視確認した。

テンプレートとスクリプトはMIT、GeistとJetBrains MonoはSIL OFL 1.1。配布元の許諾文を`licenses/`へ保存している。各ブランドのロゴは色を変更せず使用し、USB・サーバー等の概念にはLucideの汎用ピクトグラムを使った。ブランド名・ロゴの商標は各権利者に帰属する。

アイコンの配布元:

- [svgl](https://svgl.app/): HTML5、JavaScript、Python、Flask、Git、GitHub
- [devicon](https://github.com/devicons/devicon): CSS3、Arduino、C++、VS Code
- [gilbarbara/logos](https://github.com/gilbarbara/logos): PlatformIO
- [Lucide](https://lucide.dev/): USB、JSON、ファイル、シミュレーション、LED、サーバー、ブラウザ

WaitressやpySerialに付けた画像は役割を示すピクトグラムであり、それらの公式ロゴではない。

## 図を更新する

以下はmacOS/Linuxでの例。ツールは一時フォルダーに用意し、アプリの`requirements.txt`には追加しない。

```sh
git clone https://github.com/caru-ini/stack-diagram.git /tmp/aomori-stack-diagram
git -C /tmp/aomori-stack-diagram checkout 75dbd3e3c6fe28844322e6064d3a947b870a6c61
python3 -m venv /tmp/aomori-diagram-tools
/tmp/aomori-diagram-tools/bin/python -m pip install playwright==1.64.1
PLAYWRIGHT_BROWSERS_PATH=/tmp/aomori-diagram-browser /tmp/aomori-diagram-tools/bin/python -m playwright install chromium --only-shell
```

ロゴ・ピクトグラムを取得する（取得時だけネット接続が必要）。

```sh
python3 /tmp/aomori-stack-diagram/skills/stack-diagram/scripts/fetch_icons.py /tmp/aomori-diagram-icons \
  html5 css3 javascript python flask arduino cplusplus platformio vscode git github \
  serial:lucide/usb data:lucide/file-json assets:lucide/files simulation:lucide/monitor-play \
  led:lucide/lightbulb server:lucide/server browser:lucide/app-window
```

`campus-guide.source.html`のラベル・座標・矢印を編集してから、プロジェクト直下で実行する。

```sh
python3 /tmp/aomori-stack-diagram/skills/stack-diagram/scripts/build.py \
  docs/diagrams/campus-guide.source.html /tmp/aomori-diagram-icons docs/diagrams/campus-guide.html \
  --fonts /tmp/aomori-stack-diagram/skills/stack-diagram/assets/fonts
PLAYWRIGHT_BROWSERS_PATH=/tmp/aomori-diagram-browser /tmp/aomori-diagram-tools/bin/python \
  /tmp/aomori-stack-diagram/skills/stack-diagram/scripts/render_png.py \
  docs/diagrams/campus-guide.html docs/diagrams/campus-guide.png --scale 2 --single
```

暗いテーマは、同じHTMLにテーマ属性を付けた一時コピーから書き出す。テーマ切り替え直後の描画で一部ロゴが消える問題を避けるため、各テーマを初期表示した状態で別々に描画している。

```sh
python3 - <<'PY'
from pathlib import Path
source = Path('docs/diagrams/campus-guide.html').read_text(encoding='utf-8')
Path('/tmp/aomori-diagram-dark.html').write_text(
    source.replace('<html lang="ja"', '<html lang="ja" data-theme="dark"'), encoding='utf-8')
PY
PLAYWRIGHT_BROWSERS_PATH=/tmp/aomori-diagram-browser /tmp/aomori-diagram-tools/bin/python \
  /tmp/aomori-stack-diagram/skills/stack-diagram/scripts/render_png.py \
  /tmp/aomori-diagram-dark.html docs/diagrams/campus-guide-dark.png --scale 2 --single
```

PNG両方を開き、日本語の字形・改行、ロゴの欠落、文字と矢印の重なり、枠からのはみ出しを確認する。配線・通信を変更したときはREADME本文と図を同時に更新する。

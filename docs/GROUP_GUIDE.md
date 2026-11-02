# グループ向け：ダウンロードと起動

GitHubアカウントもGitのインストールも不要です。説明はGitHub上で読めます。検索画面を操作する場合は、ダウンロードしたアプリを各自のPCで起動します。

## まず見る・ダウンロードする

- [プロジェクトの説明と構成図](https://github.com/880null/aomoriuniv-campus-guide#readme)
- [最新版ZIPをダウンロード](https://github.com/880null/aomoriuniv-campus-guide/archive/refs/heads/main.zip)

ZIPをダウンロードし、フォルダー全体を展開してください。WindowsではZIPを右クリックして「すべて展開」、MacではZIPをダブルクリックします。WindowsではZIPの中から直接起動せず、展開後のフォルダーを使います。

## Arduinoがなくても画面を試せる

1. [Python公式サイト](https://www.python.org/downloads/)からPython 3.10以上をインストールします。初回の準備時はインターネット接続が必要です。
2. 展開したフォルダーを開き、Windowsは`start.bat`、Macは`start.command`をダブルクリックします。
3. ブラウザが開いたら、画面下の「接続・動作モードの設定」で「シミュレーション」を選びます。Arduino未接続でもアプリは起動します。
4. `5301`や`保健室`を検索し、結果を選択します。地図・建物・階・案内図と、模擬LED表示を確認できます。
5. 終了時は、起動時に開いたターミナルで`Ctrl+C`を押します。

シミュレーションは画面上の動作確認です。実物のLEDへ電気信号は送りません。画面の`frontend/index.html`を直接開くのではなく、起動ファイルを使ってください。アプリのURLは`http://127.0.0.1:5050/`です。

最初からシミュレーションにする場合は、展開したフォルダーをターミナルで開き、次を実行します。

```sh
# Mac
zsh ./start.command --simulate
```

```bat
rem Windows（コマンドプロンプト）
start.bat --simulate
```

Macで実行権限のエラーが出た場合も、上記の`zsh`コマンドで起動できます。Pythonが見つからない場合は、Macでは`python3 --version`、Windowsでは`py -3 --version`または`python --version`でインストール状態を確認してください。

## 実物のLEDを動かす担当の方へ

Arduino Uno R3への初回書き込みにはArduino IDE 2かPlatformIOが必要です。[READMEの初回準備](../README.md#arduinoの初回準備)と[配線図・ピン設定](HARDWARE.md)を確認してください。`.ino`だけでなく、`firmware/CampusGuide/`内のファイルをまとめて使います。

配線は1号館D2、3号館D3、5号館D4、6号館D5、7号館D6、レストラン棟D7（仮設定）です。4号館のLEDは未実装です。実機のUSB通信・配線・点灯の確認状況は[OS別検証記録](PLATFORM_VALIDATION.md)を参照してください。

## 更新版を受け取る

同じダウンロードリンクから、その時点の最新版を取得できます。新しいZIPは別フォルダーへ展開して使うと、変更したファイルを上書きせず比較できます。GitHubアカウントなしで閲覧・ダウンロードできますが、GitHub上での変更の投稿やIssueの作成にはアカウントが必要です。

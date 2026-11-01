# 開発指示

## 目的
青森大学「プログラミングワークショップⅡ」の展示用キャンパスガイド。
仕様は docs/REQUIREMENTS.md、通信契約は docs/ARCHITECTURE.md を参照する。

## 守ること
- フロントは HTML/CSS/JavaScript、バックエンドは Python/Flask/pySerial、Uno は PlatformIO/Arduino C++。
- Arduino への接続はバックエンドだけが行う。Web Serial API は使用しない。
- 配線設定は A(1号館)=D2、B(3号館)=D3、D(5号館)=D4、E(6号館)=D5、F(7号館)=D6、H(レストラン棟)=D7。同時に1個だけ点灯する。0は全消灯。
- レストラン棟のD7はユーザー指定の仮設定。実配線の確認済みとは扱わない。
- C(4号館)はLED未実装。pin=nullとし、実機点灯は無効にする。シミュレーションと施設情報表示は維持する。
- 起動識別子はREADY:CAMPUS:3。古い配線のファームウェアを接続成功として扱わない。
- シリアルプロトコルを変えるときは Python、Arduino、仕様書、テストを同時に更新する。
- 実機の応答なしに点灯成功と表示しない。未接続時の物理LED状態は不明とする。
- 未確認の教室・施設情報を推測で登録しない。data/rooms.json には確認元と確認日を持つデータだけを登録する。
- シミュレーションと実機を明確に表示し、シミュレーションではシリアルへ送信しない。
- 初学者が読める小さなモジュールに分け、重要な処理には日本語コメントを書く。
- ローカルUSB展示用。サーバーを外部公開せず、秘密情報や仮想環境をGitに追加しない。
- ユーザーの既存変更を上書きしない。実機未確認の動作を検証済みと報告しない。

## 構成
- backend/: API、データ読み込み、排他制御付きLEDコントローラー
- frontend/: HTMLと静的ファイル。外部CDNへの依存なし
- firmware/: Arduino IDE / PlatformIO共通のUnoファームウェア。実装はCampusGuide/src/main.cppに一本化する
- data/: 施設、地図メタデータ、確認済み教室
- scripts/: 仮想環境作成と起動
- tests/: unittest。実在しない教室のテストデータは一時ディレクトリだけに作る

## 確認コマンド
```sh
.venv/bin/python -m unittest discover -s tests -v
node --check frontend/static/app.js
cd firmware && pio run
```
最後のコマンドにはPlatformIOとAVRツールチェーンが必要。
変更報告にはファイル、動作、確認結果、未確認事項を記載する。

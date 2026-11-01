# 配線と書き込み

Arduino Uno R3、LED×6、抵抗220〜330Ω×6、ブレッドボード、ジャンパーワイヤー、データ通信可能なUSBケーブル。
当初は7施設を予定していたが、4号館はLED未実装。レストラン棟はユーザー指定でD7に仮設定しているため、実配線を確認する。

| 記号 | 建物 | Uno出力 |
| --- | --- | --- |
| A | 1号館 | D2 |
| B | 3号館 | D3 |
| C | 4号館 | LED未実装（制御しない） |
| D | 5号館 | D4 |
| E | 6号館 | D5 |
| F | 7号館 | D6 |
| H | レストラン棟 | D7（仮設定） |

各回路: `デジタルピン → 抵抗 → LEDアノード（長い足） → LEDカソード（短い足） → GND`。
全LEDのGNDを共通化する。抵抗はLEDごとに1本必要。配線はUSB電源を外して行う。
D0/D1はUSBシリアルに使うため接続しない。通常は選択した1個だけ点灯する。
4号館へ接続先を割り当てない。レストラン棟の設定値はD7で、D6は7号館に使用する。D8は出力として初期化しない。

## 初回の書き込み

### Arduino IDEを使う場合

1. GitHubの「Code → Download ZIP」で取得し、ZIP全体を展開する。Gitのインストールは不要。
2. Arduino IDE 2を導入し、`firmware/CampusGuide/CampusGuide.ino`を開く。
3. Uno R3をデータ通信可能なUSBケーブルで接続する。
4. 必要に応じボードマネージャーで「Arduino AVR Boards」を導入する。
5. ボードに「Arduino Uno」、ポートに接続したUnoのポートを指定し、「書き込み」を押す。
6. 書き込み完了後、シリアルモニターを閉じる。
7. プロジェクト直下のMac用`start.command` / Windows用`start.bat`を開く。

`.ino`だけを取り出さず、`CampusGuide/src/main.cpp`も含めフォルダーごと使用する。
実装はこのC++ファイルにあり、Arduino IDEが自動でビルドする。
Arduino IDEは基板のプログラムを書き込む。PC上のFlaskアプリは起動ファイルで別に立ち上げる。
PC側にはPython 3.10以上が必要で、初回の依存パッケージ取得にはインターネット接続が必要。

公式手順: https://support.arduino.cc/hc/en-us/articles/4733418441116-Upload-a-sketch-in-Arduino-IDE
スケッチ構成の仕様: https://docs.arduino.cc/arduino-cli/sketch-specification/

### PlatformIOを使う場合

1. VS CodeにPlatformIO IDE拡張を導入する。
2. firmware/をPlatformIOプロジェクトとして開く。
3. Uno R3をUSB接続し、Build → Upload。
4. シリアルモニターを閉じて、PC側の起動ファイルを開く。

CLIで行う場合:
```sh
cd firmware
pio run
pio run --target upload
pio device monitor --baud 9600
```
複数機器がある場合は`pio run --target upload --upload-port COM3`等で指定する。
書き込み済みのプログラムは電源投入時に自動実行される。
別のPCへ基板をつなぎ替えても、通常は再書き込み不要。PC側のPython環境とアプリは移動先にも用意する。
今回の配線変更を反映するには、新しいスケッチの書き込みが必要。旧版の起動通知v1/v2を新アプリは受理しない。

## 手動の通信確認
9600bps、LFで送信。接続直後は`READY:CAMPUS:3`。
`A`でD2だけ点灯し`OK:A`、`?`で`STATE:A`、`0`で全消灯し`OK:0`。
`D`は5号館/D4、`E`は6号館/D5、`F`は7号館/D6。
`H`はレストラン棟/D7。未実装の`C`、対象外の`G`、複数文字の`AB`は`ERR:INVALID`。有効な受信が10秒ないと全消灯する。

## 実機受入チェック（現時点では未実施）
- 起動/RESETで全消灯、A/B/D/E/F/Hで指定の1個だけ点灯。
- Cを送っても他のLEDを点灯させない。
- 0で全消灯、不正入力で状態が変わらない。
- 通信停止から10秒で消灯。
- USB抜去で画面がエラーとなり、再接続で復帰。
- 画面を閉じた場合とCtrl+Cで止めた場合の消灯。
- Mac/Windowsの展示用PCで起動と再接続。

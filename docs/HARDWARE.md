# 配線と書き込み

Arduino Uno R3、LED×7、抵抗220〜330Ω×7、ブレッドボード、ジャンパーワイヤー、データ通信可能なUSBケーブル。

| 記号 | 建物 | Uno出力 |
| --- | --- | --- |
| A | 1号館 | D2 |
| B | 3号館 | D3 |
| C | 4号館 | D4 |
| D | 5号館 | D5 |
| E | 6号館 | D6 |
| F | 7号館 | D7 |
| H | レストラン棟 | D8 |

各回路: `デジタルピン → 抵抗 → LEDアノード（長い足） → LEDカソード（短い足） → GND`。
全LEDのGNDを共通化する。抵抗はLEDごとに1本必要。配線はUSB電源を外して行う。
D0/D1はUSBシリアルに使うため接続しない。通常は選択した1個だけ点灯する。

## 初回の書き込み
1. VS CodeにPlatformIO IDE拡張を導入する。
2. firmware/をPlatformIOプロジェクトとして開く。
3. Uno R3をUSB接続し、Build → Upload。
4. アプリとシリアルモニターの同時利用は避け、モニターを閉じてアプリを起動する。

CLIで行う場合:
```sh
cd firmware
pio run
pio run --target upload
pio device monitor --baud 9600
```
複数機器がある場合は`pio run --target upload --upload-port COM3`等で指定する。
書き込み済みのプログラムは電源投入時に自動実行される。

## 手動の通信確認
9600bps、LFで送信。接続直後は`READY:CAMPUS:1`。
`A`でD2だけ点灯し`OK:A`、`?`で`STATE:A`、`0`で全消灯し`OK:0`。
`G`や`AB`は`ERR:INVALID`。有効な受信が10秒ないと全消灯する。

## 実機受入チェック（現時点では未実施）
- 起動/RESETで全消灯、A/B/C/D/E/F/Hで指定の1個だけ点灯。
- 0で全消灯、不正入力で状態が変わらない。
- 通信停止から10秒で消灯。
- USB抜去で画面がエラーとなり、再接続で復帰。
- 画面を閉じた場合とCtrl+Cで止めた場合の消灯。
- Mac/Windowsの展示用PCで起動と再接続。

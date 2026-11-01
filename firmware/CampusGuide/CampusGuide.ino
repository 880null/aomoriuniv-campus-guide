/*
 * 青森大学インタラクティブキャンパスガイド（Arduino Uno R3）
 *
 * 1. このファイルをArduino IDE 2で開く。
 * 2. ボード「Arduino Uno」と接続したUSBポートを選ぶ。
 * 3. 「書き込み」を押す。
 * 4. シリアルモニターを閉じ、PC側のstart.command / start.batを開く。
 *
 * 実際のsetup() / loop()はsrc/main.cppにある。
 * Arduino IDEはsrc/内のC++ファイルも自動でビルドする。
 * このファイルだけを取り出さず、CampusGuideフォルダーごと使用する。
 * PCのWebアプリはArduino IDEとは別に起動する。
 */
#include <Arduino.h>

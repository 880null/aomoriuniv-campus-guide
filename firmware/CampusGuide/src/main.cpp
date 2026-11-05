#include <Arduino.h>

// Arduino IDEとPlatformIOで共通の実装を使用する。

namespace {
// 1号館D2 / 3号館D3 / 5号館D4 / 6号館D5 / 7号館D6。
// 4号館(C)・レストラン棟(H)はLED未実装のため制御しない。
const char BUILDINGS[] = {'A', 'B', 'D', 'E', 'F'};
const uint8_t LED_PINS[] = {2, 3, 4, 5, 6};
const uint8_t LED_COUNT = sizeof(LED_PINS) / sizeof(LED_PINS[0]);
const unsigned long WATCHDOG_MS = 10000;
char active = '0';
unsigned long lastCommandAt = 0;
char received = '\0';
uint8_t receivedCount = 0;
bool invalidLine = false;
bool receivedCR = false;

void setLeds(char command) {
  // 先に全消灯してから1個だけ点灯する。
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    digitalWrite(LED_PINS[i], LOW);
  }
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    if (command == BUILDINGS[i]) digitalWrite(LED_PINS[i], HIGH);
  }
  active = command;
}

bool isSelection(char command) {
  if (command == '0') return true;
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    if (command == BUILDINGS[i]) return true;
  }
  return false;
}

void finishLine() {
  if (invalidLine || receivedCount != 1) {
    Serial.println(F("ERR:INVALID"));
  } else if (received == '?') {
    lastCommandAt = millis();
    Serial.print(F("STATE:"));
    Serial.println(active);
  } else if (isSelection(received)) {
    setLeds(received);
    lastCommandAt = millis();
    Serial.print(F("OK:"));
    Serial.println(active);
  } else {
    Serial.println(F("ERR:INVALID"));
  }
  receivedCount = 0;
  received = '\0';
  invalidLine = false;
  receivedCR = false;
}
}  // namespace

void setup() {
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    digitalWrite(LED_PINS[i], LOW);
    pinMode(LED_PINS[i], OUTPUT);
  }
  setLeds('0');
  Serial.begin(9600);
  lastCommandAt = millis();
  Serial.println(F("READY:CAMPUS:4"));
}

void loop() {
  // unsignedの差分で、millis()の桁あふれ後も経過時間を判定する。
  if (active != '0' && millis() - lastCommandAt >= WATCHDOG_MS) setLeds('0');

  // 一度に処理する量を制限し、大量受信中も監視タイマーを実行する。
  for (uint8_t count = 0; count < 32 && Serial.available() > 0; ++count) {
    char value = static_cast<char>(Serial.read());
    if (value == '\n') {
      finishLine();
    } else if (value == '\r') {
      if (receivedCR || receivedCount != 1) invalidLine = true;
      receivedCR = true;
    } else {
      if (receivedCR || receivedCount >= 1) invalidLine = true;
      if (receivedCount == 0) received = value;
      // カウンターを飽和させ、長すぎる入力による桁あふれを防ぐ。
      if (receivedCount < 2) ++receivedCount;
    }
  }
}

#include <cassert>
#include <limits>
#include <string>
#include "../../firmware/CampusGuide/src/main.cpp"

void send(const std::string &line) {
  Serial.output.clear();
  for (char c : line) Serial.input.push_back(c);
  while (Serial.available()) loop();
}

void expectOnly(int pin) {
  for (int p = 2; p <= 6; ++p) assert(outputs[p] == (p == pin ? HIGH : LOW));
  assert(outputs[7] == HIGH && outputs[8] == HIGH);  // 未使用ピンは変更しない。
}

int main() {
  outputs[7] = outputs[8] = HIGH;
  setup();
  assert(Serial.baud == 9600);
  assert(Serial.output == "READY:CAMPUS:4\r\n");
  for (int pin = 2; pin <= 6; ++pin) assert(modes[pin] == OUTPUT);
  assert(modes[7] != OUTPUT && modes[8] != OUTPUT);
  expectOnly(-1);
  const std::string keys = "ABDEF";
  for (int i = 0; i < 5; ++i) {
    send(std::string(1, keys[i]) + "\n");
    assert(Serial.output == "OK:" + std::string(1, keys[i]) + "\r\n");
    expectOnly(i + 2);
  }
  send("?\n");
  assert(Serial.output == "STATE:F\r\n");
  send("A\r\n");
  assert(Serial.output == "OK:A\r\n");
  expectOnly(2);
  for (const auto &line : {"C\n", "H\n", "G\n", "AB\n", "\n", "A\rB\n", "\rA\n", "a\n"}) {
    send(line);
    assert(Serial.output == "ERR:INVALID\r\n");
    expectOnly(2);
  }
  send(std::string(1000, 'A') + "\n");
  assert(Serial.output == "ERR:INVALID\r\n");
  expectOnly(2);
  clockMs = 9999;
  loop();
  expectOnly(2);
  clockMs = 10000;
  loop();
  expectOnly(-1);
  send("?\n");
  assert(Serial.output == "STATE:0\r\n");
  send("B\n");
  clockMs = 19000;
  send("?\n");  // 状態確認で監視時間を延長する。
  clockMs = 20000;
  loop();
  expectOnly(3);
  send("0\n");
  assert(Serial.output == "OK:0\r\n");
  expectOnly(-1);

  // unsigned longの桁あふれを跨いでも、10秒未満では消灯しない。
  clockMs = std::numeric_limits<unsigned long>::max() - 5000;
  send("A\n");
  clockMs += 9999;
  loop();
  expectOnly(2);
  clockMs += 1;
  loop();
  expectOnly(-1);
}

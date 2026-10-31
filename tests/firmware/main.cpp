#include <cassert>
#include <string>
#include "../../firmware/src/main.cpp"

void send(const std::string &line) {
  Serial.output.clear();
  for (char c : line) Serial.input.push_back(c);
  while (Serial.available()) loop();
}

void expectOnly(int pin) {
  for (int p = 2; p <= 8; ++p) assert(outputs[p] == (p == pin ? HIGH : LOW));
}

int main() {
  setup();
  assert(Serial.baud == 9600);
  assert(Serial.output == "READY:CAMPUS:1\n");
  expectOnly(-1);
  const std::string keys = "ABCDEFH";
  for (int i = 0; i < 7; ++i) {
    send(std::string(1, keys[i]) + "\n");
    assert(Serial.output == "OK:" + std::string(1, keys[i]) + "\n");
    expectOnly(i + 2);
  }
  send("?\n");
  assert(Serial.output == "STATE:H\n");
  send("A\r\n");
  assert(Serial.output == "OK:A\n");
  expectOnly(2);
  for (const auto &line : {"G\n", "AB\n", "\n", "A\rB\n", "\rA\n", "a\n"}) {
    send(line);
    assert(Serial.output == "ERR:INVALID\n");
    expectOnly(2);
  }
  send(std::string(1000, 'A') + "\n");
  assert(Serial.output == "ERR:INVALID\n");
  expectOnly(2);
  clockMs = 9999;
  loop();
  expectOnly(2);
  clockMs = 10000;
  loop();
  expectOnly(-1);
  send("?\n");
  assert(Serial.output == "STATE:0\n");
  send("B\n");
  clockMs = 19000;
  send("?\n");  // 状態確認で監視時間を延長する。
  clockMs = 20000;
  loop();
  expectOnly(3);
  send("0\n");
  assert(Serial.output == "OK:0\n");
  expectOnly(-1);
}

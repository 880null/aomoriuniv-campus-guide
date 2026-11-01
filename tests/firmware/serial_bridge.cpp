// 検証専用: 実際のmain.cppをOSの仮想シリアルポートへ接続する。
// AVR命令、USB回路、電圧、LEDの実物はエミュレートしない。
#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <poll.h>
#include <string>
#include <unistd.h>
#include "../../firmware/CampusGuide/src/main.cpp"

namespace {
using Clock = std::chrono::steady_clock;
auto started = Clock::now();
unsigned long offsetMs = 0;

void resetFirmware() {
  started = Clock::now();
  offsetMs = 0;
  clockMs = 0;
  received = '\0';
  receivedCount = 0;
  invalidLine = false;
  receivedCR = false;
  Serial.input.clear();
  Serial.output.clear();
  setup();
}

bool flushSerial(int fd) {
  size_t sent = 0;
  while (sent < Serial.output.size()) {
    ssize_t count = write(fd, Serial.output.data() + sent, Serial.output.size() - sent);
    if (count < 0 && errno == EINTR) continue;
    if (count <= 0) return false;
    sent += static_cast<size_t>(count);
  }
  Serial.output.clear();
  return true;
}
}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  int port = std::atoi(argv[1]);
  pollfd descriptors[] = {{port, POLLIN, 0}, {STDIN_FILENO, POLLIN, 0}};
  while (true) {
    int ready = poll(descriptors, 2, 5);
    if (ready < 0 && errno == EINTR) continue;
    if (ready < 0 || descriptors[1].revents & POLLHUP) return 0;

    if (descriptors[0].revents & POLLIN) {
      char buffer[128];
      ssize_t count = read(port, buffer, sizeof(buffer));
      for (ssize_t i = 0; i < count; ++i) Serial.input.push_back(buffer[i]);
    }

    bool report = descriptors[1].revents & POLLIN;
    if (report) {
      std::string command;
      if (!std::getline(std::cin, command)) return 0;
      if (command == "RESET") resetFirmware();
      else if (command.rfind("ADVANCE ", 0) == 0) offsetMs += std::stoul(command.substr(8));
      else if (command != "PINS") return 2;
    }

    clockMs = offsetMs + static_cast<unsigned long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count());
    do {
      loop();
    } while (Serial.available());
    if (!flushSerial(port)) return 3;
    if (report) {
      // ピンの検査は別経路で行い、アプリのシリアル通信に検査用コマンドを混ぜない。
      for (int pin = 2; pin <= 8; ++pin) std::cout << outputs[pin];
      std::cout << std::endl;
    }
  }
}

#pragma once
#include <cstdint>
#include <deque>
#include <string>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define F(value) value

inline unsigned long clockMs = 0;
inline int outputs[20] = {};
inline unsigned long millis() { return clockMs; }
inline void pinMode(uint8_t, int) {}
inline void digitalWrite(uint8_t pin, int value) { outputs[pin] = value; }

struct FakeSerial {
  std::deque<char> input;
  std::string output;
  unsigned long baud = 0;
  void begin(unsigned long value) { baud = value; }
  int available() { return static_cast<int>(input.size()); }
  int read() { char c = input.front(); input.pop_front(); return c; }
  void print(const char *text) { output += text; }
  void println(const char *text) { output += text; output += '\n'; }
  void println(char value) { output += value; output += '\n'; }
};
inline FakeSerial Serial;

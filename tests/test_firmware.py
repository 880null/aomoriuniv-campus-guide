from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class FirmwareLogicTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("clang++") or shutil.which("g++"), "C++コンパイラが未導入")
    def test_actual_firmware_parser_pins_and_watchdog_with_mock_arduino(self):
        # 実際のmain.cppをスタブArduino上で動かす。実機/AVRビルドの代替ではない。
        with tempfile.TemporaryDirectory() as directory:
            binary = str(Path(directory) / "firmware-test")
            compiler = shutil.which("clang++") or shutil.which("g++")
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "tests/firmware"),
                            str(ROOT / "tests/firmware/main.cpp"), "-o", binary], check=True)
            subprocess.run([binary], check=True)

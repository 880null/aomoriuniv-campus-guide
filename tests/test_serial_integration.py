"""Flask→実pySerial→OS仮想ポート→実main.cppの結合テスト。実機検証ではない。"""

from pathlib import Path
import os
import select
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest

import serial

from backend.app import create_app
from backend.controller import LedController

ROOT = Path(__file__).resolve().parent.parent
COMPILER = shutil.which("clang++") or shutil.which("g++")


class NativeUno:
    def __init__(self, binary):
        import tty

        master, self.slave = os.openpty()
        tty.setraw(self.slave)
        self.device = os.ttyname(self.slave)
        self.lock = threading.Lock()
        try:
            self.process = subprocess.Popen(
                [binary, str(master)], pass_fds=(master,), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        finally:
            os.close(master)
        try:
            self.control("PINS")
        except Exception:
            self.close()
            raise

    def control(self, command):
        with self.lock:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            ready, _, _ = select.select([self.process.stdout], [], [], 3)
            if not ready:
                raise RuntimeError("検証用ファームウェアが応答しません。")
            pins = self.process.stdout.readline().strip()
            if len(pins) != 7 or any(bit not in "01" for bit in pins):
                raise RuntimeError(f"不正な検査応答: {pins!r}")
            return [int(bit) for bit in pins]

    def descriptor(self):
        return SimpleNamespace(device=self.device, description="Test virtual Uno", vid=0x2341, pid=0x0043)

    def open_serial(self, **kwargs):
        # pySerial本体を使う。USBのDTRリセットだけは検証用の別経路で再現する。
        device = serial.Serial(**kwargs)
        try:
            self.control("RESET")
        except Exception:
            device.close()
            raise
        return device

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()
        if self.slave is not None:
            os.close(self.slave)
            self.slave = None


@unittest.skipUnless(os.name == "posix" and COMPILER, "POSIX仮想ポートとC++コンパイラが必要")
class SerialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.binary = str(Path(cls.temporary.name) / "virtual-uno")
        subprocess.run([COMPILER, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "tests/firmware"),
                        str(ROOT / "tests/firmware/serial_bridge.cpp"), "-o", cls.binary], check=True)

    def setUp(self):
        self.board = NativeUno(self.binary)
        self.addCleanup(self.board.close)
        self.controller = LedController(
            serial_factory=lambda **kwargs: self.board.open_serial(**kwargs),
            ports_provider=lambda: [self.board.descriptor()])
        self.addCleanup(self.controller.close)
        self.client = create_app(self.controller).test_client()
        response = self.client.post("/api/connection", json={})
        self.assertEqual(response.status_code, 200, response.json)

    def assertPins(self, selected=None):
        pins = self.board.control("PINS")
        expected = [int(pin == selected) for pin in range(2, 9)]
        self.assertEqual(pins, expected)

    def test_connection_resets_and_turns_confirmed_outputs_off(self):
        self.assertPins()
        state = self.client.get("/api/status").json["status"]
        self.assertEqual(state["mode"], "real")
        self.assertTrue(state["connected"])
        self.assertEqual(state["led_state"], "off")

    def test_confirmed_buildings_and_off_through_api_and_real_serial(self):
        for key, pin in zip("ABDEFH", range(2, 8)):
            with self.subTest(building=key, pin=pin):
                response = self.client.post("/api/select", json={"building_id": key})
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(response.json["status"]["active_building"], key)
                self.assertPins(pin)
        self.assertEqual(self.client.post("/api/off", json={}).status_code, 200)
        self.assertPins()

    def test_watchdog_off_is_reflected_in_api(self):
        self.client.post("/api/select", json={"building_id": "D"})
        self.assertEqual(self.board.control("ADVANCE 10001"), [0] * 7)
        state = self.client.get("/api/status").json["status"]
        self.assertEqual(state["led_state"], "off")
        self.assertIn("変化", state["notice"])

    def test_status_heartbeat_keeps_selected_output_on(self):
        self.client.post("/api/select", json={"building_id": "F"})
        for _ in range(5):
            self.board.control("ADVANCE 8000")
            state = self.client.get("/api/status").json["status"]
            self.assertEqual(state["active_building"], "F")
            self.assertPins(6)

    def test_invalid_wire_input_does_not_change_selected_output(self):
        self.client.post("/api/select", json={"building_id": "A"})
        wire = self.controller._serial
        for payload in (b"G\n", b"AB\n", b"A" * 1000 + b"\n"):
            with self.subTest(payload_size=len(payload)):
                wire.write(payload)
                self.assertEqual(wire.read_until(b"\n"), b"ERR:INVALID\r\n")
                self.assertPins(2)
        wire.write(b"B")
        self.assertEqual(self.board.control("PINS"), [1, 0, 0, 0, 0, 0, 0])
        wire.write(b"\r\n")
        self.assertEqual(wire.read_until(b"\n"), b"OK:B\r\n")
        self.assertPins(3)

    def test_disconnect_is_unknown_and_single_reconnect_recovers(self):
        self.client.post("/api/select", json={"building_id": "A"})
        self.board.close()
        response = self.client.post("/api/select", json={"building_id": "B"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["status"]["led_state"], "unknown")
        self.board = NativeUno(self.binary)
        self.addCleanup(self.board.close)
        response = self.client.post("/api/connection", json={})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertPins()
        self.client.post("/api/select", json={"building_id": "F"})
        self.assertPins(6)

    def test_stale_connection_can_be_replaced_without_status_poll(self):
        self.client.post("/api/select", json={"building_id": "A"})
        self.board.close()
        self.board = NativeUno(self.binary)
        self.addCleanup(self.board.close)
        response = self.client.post("/api/connection", json={})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json["status"]["notice"])
        self.assertPins()

    def test_unexpected_board_reset_is_detected_and_reconnects(self):
        self.client.post("/api/select", json={"building_id": "E"})
        self.board.control("RESET")
        self.assertPins()
        state = self.client.get("/api/status").json["status"]
        self.assertFalse(state["connected"])
        self.assertEqual(state["led_state"], "unknown")
        self.assertEqual(self.client.post("/api/connection", json={}).status_code, 200)
        self.assertPins()

    def test_simulation_switch_and_shutdown_turn_physical_outputs_off(self):
        self.client.post("/api/select", json={"building_id": "F"})
        response = self.client.post("/api/mode", json={"mode": "simulation"})
        self.assertEqual(response.status_code, 200)
        self.assertPins()
        self.client.post("/api/select", json={"building_id": "H"})
        self.assertPins()
        self.client.post("/api/mode", json={"mode": "real"})
        self.client.post("/api/select", json={"building_id": "D"})
        self.assertPins(4)
        self.controller.close()
        self.assertPins()

    def test_repeated_selections_keep_ack_and_outputs_in_sync(self):
        for key in "ABDEFH" * 24:
            response = self.client.post("/api/select", json={"building_id": key})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json["status"]["active_building"], key)
        self.assertPins(7)

    def test_unconfirmed_buildings_cannot_light_a_different_building(self):
        self.client.post("/api/select", json={"building_id": "D"})
        for key in "C":
            with self.subTest(building=key):
                response = self.client.post("/api/select", json={"building_id": key})
                self.assertEqual(response.status_code, 400)
                self.assertIn("未確認", response.json["error"])
                self.assertPins(4)
                wire = self.controller._serial
                wire.write((key + "\n").encode("ascii"))
                self.assertEqual(wire.read_until(b"\n"), b"ERR:INVALID\r\n")
                self.assertPins(4)

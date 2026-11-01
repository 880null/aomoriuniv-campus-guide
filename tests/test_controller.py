from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock

import serial

from backend.controller import ControllerError, LedController


def uno(device="/dev/test-uno"):
    return SimpleNamespace(device=device, description="Arduino Uno", vid=0x2341, pid=0x0043)


class FakeSerial:
    """実USBを使わず、通信契約と障害時の扱いを検証する。"""
    def __init__(self, **kwargs):
        self.is_open = True
        self.timeout = kwargs["timeout"]
        self.responses = [b"READY:CAMPUS:3\n"]
        self.commands = []
        self.active = "0"
        self.bad_response = None
        self.write_failure = False

    def write(self, payload):
        if self.write_failure:
            raise serial.SerialException("test disconnected")
        command = payload.decode("ascii").strip()
        self.commands.append(command)
        if self.bad_response is not None:
            self.responses.append(self.bad_response)
        elif command == "?":
            self.responses.append(f"STATE:{self.active}\n".encode())
        else:
            self.active = command
            self.responses.append(f"OK:{command}\n".encode())
        return len(payload)

    def read_until(self, terminator, size):
        time.sleep(0.001)
        return self.responses.pop(0) if self.responses else b""

    def close(self):
        self.is_open = False


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.factory = Mock(side_effect=FakeSerial)
        self.controller = LedController(serial_factory=self.factory, ports_provider=lambda: [uno()])
        self.addCleanup(self.controller.close)

    def connected(self):
        self.controller.connect()
        return self.controller._serial

    def test_initial_disconnected_state_is_unknown(self):
        self.assertEqual(self.controller.snapshot()["led_state"], "unknown")

    def test_connection_handshake_and_off_ack(self):
        state = self.controller.connect()
        self.assertTrue(state["connected"])
        self.assertEqual(state["led_state"], "off")
        self.assertEqual(self.controller._serial.commands, ["0"])
        self.assertEqual(self.factory.call_args.kwargs["baudrate"], 9600)

    def test_each_selection_then_off(self):
        self.connected()
        for key in "ABDEFH":
            self.assertEqual(self.controller.select(key)["active_building"], key)
        self.assertEqual(self.controller.select("0")["led_state"], "off")

    def test_no_device(self):
        controller = LedController(ports_provider=lambda: [])
        with self.assertRaises(ControllerError):
            controller.connect()
        self.assertEqual(controller.snapshot()["led_state"], "unknown")

    def test_ambiguous_ports_do_not_open_any_device(self):
        controller = LedController(serial_factory=self.factory, ports_provider=lambda: [uno("one"), uno("two")])
        with self.assertRaises(ControllerError):
            controller.connect()
        self.factory.assert_not_called()

    def test_explicit_port_cannot_be_serial_url(self):
        with self.assertRaises(ControllerError):
            self.controller.connect("socket://example.com:9999")
        self.factory.assert_not_called()

    def test_bad_ack_clears_connection_and_does_not_claim_on(self):
        device = self.connected()
        device.bad_response = b"OK:B\n"
        with self.assertRaises(ControllerError):
            self.controller.select("A")
        self.assertFalse(device.is_open)
        self.assertEqual(self.controller.snapshot()["led_state"], "unknown")

    def test_timeout_and_malformed_responses(self):
        for response in (b"", b"OK:A", b"\xff\n", b"ERR:INVALID\n"):
            with self.subTest(response=response):
                device = self.connected()
                device.bad_response = response
                with self.assertRaises(ControllerError):
                    self.controller.select("A")
                self.assertFalse(self.controller.snapshot()["connected"])

    def test_write_error_detected_by_status(self):
        device = self.connected()
        self.controller.select("D")
        device.write_failure = True
        state = self.controller.status()
        self.assertFalse(state["connected"])
        self.assertIsNone(state["active_building"])
        self.assertIn("通信エラー", state["error"])

    def test_watchdog_or_external_off_is_reflected(self):
        device = self.connected()
        self.controller.select("D")
        device.active = "0"
        state = self.controller.status()
        self.assertEqual(state["led_state"], "off")
        self.assertIn("変化", state["notice"])

    def test_simulation_never_opens_or_writes_usb(self):
        controller = LedController("simulation", serial_factory=self.factory)
        for key in "ABCDEFH0":
            controller.select(key)
            controller.status()
        with self.assertRaises(ControllerError):
            controller.connect()
        controller.close()
        self.factory.assert_not_called()

    def test_real_to_simulation_turns_off_before_close(self):
        device = self.connected()
        self.controller.select("F")
        state = self.controller.set_mode("simulation")
        self.assertEqual(device.commands[-1], "0")
        self.assertFalse(device.is_open)
        self.assertEqual(state["mode"], "simulation")

    def test_failed_off_does_not_switch_mode(self):
        device = self.connected()
        device.write_failure = True
        with self.assertRaises(ControllerError):
            self.controller.set_mode("simulation")
        self.assertEqual(self.controller.mode, "real")

    def test_shutdown_turns_off(self):
        device = self.connected()
        self.controller.select("A")
        self.controller.close()
        self.assertEqual(device.commands[-1], "0")
        self.assertFalse(device.is_open)

    def test_concurrent_commands_do_not_mix_responses(self):
        self.connected()
        with ThreadPoolExecutor(max_workers=7) as pool:
            results = list(pool.map(self.controller.select, "ABDEFH" * 3))
        self.assertTrue(all(r["connected"] for r in results))
        self.assertEqual([r["active_building"] for r in results], list("ABDEFH" * 3))

    def test_unconfirmed_pins_are_blocked_without_serial_write(self):
        device = self.connected()
        self.controller.select("A")
        commands = device.commands.copy()
        for key in "C":
            with self.subTest(building=key):
                with self.assertRaisesRegex(ValueError, "未確認"):
                    self.controller.select(key)
                self.assertEqual(device.commands, commands)
                self.assertEqual(self.controller.snapshot()["active_building"], "A")

    def test_old_wiring_firmware_is_rejected(self):
        for version in (1, 2):
            with self.subTest(version=version):
                device = FakeSerial(timeout=0.2)
                device.responses = [f"READY:CAMPUS:{version}\r\n".encode()]
                self.factory.side_effect = None
                self.factory.return_value = device
                with unittest.mock.patch("backend.controller.time.monotonic", side_effect=[0, 1, 5]):
                    with self.assertRaisesRegex(ControllerError, "最新スケッチ"):
                        self.controller.connect()
                self.assertEqual(device.commands, [])

    def test_reconnect_after_failure(self):
        device = self.connected()
        device.write_failure = True
        with self.assertRaises(ControllerError):
            self.controller.select("A")
        self.assertEqual(self.controller.connect()["led_state"], "off")

    def test_reconnect_recovers_stale_connection_in_one_attempt(self):
        device = self.connected()
        self.controller.select("A")
        device.write_failure = True
        # 定期照会が切断を検知する前に再接続しても、1回で新しい接続へ進む。
        state = self.controller.connect()
        self.assertTrue(state["connected"])
        self.assertEqual(state["led_state"], "off")
        self.assertIsNot(self.controller._serial, device)

    def test_fragmented_boot_notification_is_reassembled(self):
        device = FakeSerial(timeout=0.2)
        device.responses = [b"READY:CAMP", b"US:3\r\n"]
        self.factory.side_effect = None
        self.factory.return_value = device
        with unittest.mock.patch("backend.controller.time.monotonic", side_effect=range(8)):
            self.assertTrue(self.controller.connect()["connected"])

    def test_overlong_boot_line_cannot_hide_a_valid_suffix(self):
        device = FakeSerial(timeout=0.2)
        device.responses = [b"x" * 64, b"READY:CAMPUS:3\n"]
        self.factory.side_effect = None
        self.factory.return_value = device
        with unittest.mock.patch("backend.controller.time.monotonic", side_effect=range(8)):
            with self.assertRaisesRegex(ControllerError, "起動通知"):
                self.controller.connect()
        self.assertEqual(device.commands, [])

    def test_valid_boot_line_after_oversized_noise_is_accepted(self):
        device = FakeSerial(timeout=0.2)
        device.responses = [b"x" * 64, b"noise\n", b"READY:CAMPUS:3\r\n"]
        self.factory.side_effect = None
        self.factory.return_value = device
        with unittest.mock.patch("backend.controller.time.monotonic", side_effect=range(8)):
            self.assertTrue(self.controller.connect()["connected"])

    def test_wrong_firmware_handshake_is_rejected(self):
        device = FakeSerial(timeout=0.2)
        device.responses = [b"READY:OTHER\n"]
        self.factory.side_effect = None
        self.factory.return_value = device
        # 待機上限をテスト時計で短縮する。
        with unittest.mock.patch("backend.controller.time.monotonic", side_effect=[0, 1, 5]):
            with self.assertRaisesRegex(ControllerError, "起動通知"):
                self.controller.connect()
        self.assertEqual(device.commands, [])

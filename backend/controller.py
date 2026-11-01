"""ACKで実機の状態を確定する、排他制御付きLEDコントローラー。"""

import threading
import time

import serial
from serial.tools import list_ports

from backend.catalog import PIN_MAP


class ControllerError(Exception):
    pass


class LedController:
    def __init__(self, mode="real", port=None, serial_factory=None, ports_provider=None):
        if mode not in ("real", "simulation"):
            raise ValueError("modeはrealまたはsimulationです。")
        self.mode = mode
        self.preferred_port = port
        self._serial_factory = serial_factory or serial.Serial
        self._ports_provider = ports_provider or list_ports.comports
        self._lock = threading.RLock()
        self._serial = None
        self._active = None
        self._error = None
        self._notice = None
        self._port = None

    def ports(self):
        try:
            return [{"device": p.device, "description": p.description or p.device,
                     "uno": (p.vid in (0x2341, 0x2A03) and p.pid in (0x0001, 0x0043, 0x0243))
                     or "uno" in (p.description or "").lower()}
                    for p in self._ports_provider()]
        except (OSError, serial.SerialException) as exc:
            raise ControllerError(f"USBポートを取得できません: {exc}") from exc

    def snapshot(self):
        with self._lock:
            simulation = self.mode == "simulation"
            connected = self._serial is not None and self._serial.is_open
            known = simulation or connected
            return {"mode": self.mode, "connected": connected, "port": self._port,
                    "active_building": self._active if known else None,
                    "led_state": ("on" if self._active else "off") if known else "unknown",
                    "error": self._error, "notice": self._notice}

    def _drop(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except (OSError, serial.SerialException):
                pass
        self._serial = None
        self._port = None
        self._active = None

    def _fail(self, message):
        self._drop()
        self._error = message
        raise ControllerError(message)

    def _read_line(self):
        # サイズと改行を検査し、不完全な受信を成功扱いしない。
        raw = self._serial.read_until(b"\n", size=64)
        if not raw.endswith(b"\n"):
            raise ControllerError("Arduinoの応答がタイムアウトしたか、長すぎます。")
        try:
            return raw.decode("ascii").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise ControllerError("ArduinoからASCII以外の応答を受信しました。") from exc

    def _wait_for_ready(self):
        # read_untilは途中でタイムアウトすると部分行を返すため、起動待ちの間は保持する。
        pending = bytearray()
        overlong = False
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            chunk = self._serial.read_until(b"\n", size=64)
            if len(pending) + len(chunk) > 64:
                overlong = True
            if not overlong:
                pending.extend(chunk)
            if chunk.endswith(b"\n"):
                if not overlong and pending in (b"READY:CAMPUS:1\n", b"READY:CAMPUS:1\r\n"):
                    return
                # 長すぎる行はLFまで破棄する。途中の識別子だけを受理しない。
                pending.clear()
                overlong = False
        self._fail("ファームウェアの起動通知を確認できません。書き込み・9600bps・RESETを確認してください。")

    def _exchange(self, command):
        if self._serial is None or not self._serial.is_open:
            self._fail("Arduinoが未接続です。USB接続とポートを確認し、再接続してください。")
        try:
            # 送信からACK確認まで同じロック内で扱う。再送は自動で行わない。
            payload = (command + "\n").encode("ascii")
            if self._serial.write(payload) != len(payload):
                raise ControllerError("コマンドを最後まで送信できませんでした。")
            response = self._read_line()
            if command == "?":
                if response not in {f"STATE:{c}" for c in (*PIN_MAP, "0")}:
                    raise ControllerError(f"Arduinoの状態応答が不正です: {response}")
                return response[-1]
            if response != f"OK:{command}":
                raise ControllerError(f"Arduinoの応答が一致しません: {response}")
            return command
        except (OSError, serial.SerialException, ControllerError) as exc:
            self._fail(f"通信エラー: {exc} LEDの状態は不明です。再接続してください。")

    def connect(self, port=None):
        with self._lock:
            if self.mode != "real":
                raise ControllerError("シミュレーション中はUSB接続しません。実機モードへ切り替えてください。")
            # 古い接続が切れていても、1回の再接続操作で新しい接続の試行まで進める。
            previous_off_failed = False
            if self._serial is not None:
                try:
                    self._exchange("0")
                except ControllerError:
                    previous_off_failed = True
            self._drop()
            self._error = None
            self._notice = None
            try:
                ports = self.ports()
                chosen = port or self.preferred_port
                if chosen:
                    if chosen not in {p["device"] for p in ports}:
                        self._fail("指定されたUSBポートが見つかりません。ポート一覧を更新してください。")
                else:
                    candidates = [p["device"] for p in ports if p["uno"]]
                    if len(candidates) != 1:
                        self._fail("Unoを一意に検出できません。USB接続を確認し、ポートを選んで再接続してください。")
                    chosen = candidates[0]
                self._serial = self._serial_factory(
                    port=chosen, baudrate=9600, timeout=0.2, write_timeout=1)
                self._port = chosen
                # Unoはポートを開くとリセットされる。識別子を待って別機器への送信を防ぐ。
                self._wait_for_ready()
                self._serial.timeout = 1
                self._exchange("0")
                if previous_off_failed:
                    self._notice = "以前の接続では消灯を確認できませんでした。現在の接続先は初期化済みです。"
                return self.snapshot()
            except (OSError, serial.SerialException, ControllerError) as exc:
                self._fail(str(exc))

    def select(self, building_id):
        if building_id not in PIN_MAP and building_id != "0":
            raise ValueError("対象外の建物です。")
        with self._lock:
            if self.mode == "real":
                self._exchange(building_id)
            self._active = None if building_id == "0" else building_id
            self._error = None
            self._notice = None
            return self.snapshot()

    def status(self):
        with self._lock:
            if self.mode == "real" and self._serial is not None:
                try:
                    current = self._exchange("?")
                    active = None if current == "0" else current
                    if self._active != active:
                        self._notice = "実機のLED状態が変化しました。現在の状態に表示を合わせました。"
                    self._active = active
                except ControllerError:
                    pass  # GETでもエラー状態をJSONで返し、画面の定期表示を止めない。
            return self.snapshot()

    def set_mode(self, mode):
        if mode not in ("real", "simulation"):
            raise ValueError("modeはrealまたはsimulationです。")
        with self._lock:
            if mode == self.mode:
                return self.snapshot()
            unknown = self.mode == "real" and self._serial is None
            if self.mode == "real" and self._serial is not None:
                self._exchange("0")  # 消灯確認に失敗した場合、モードを勝手に切り替えない。
            self._drop()
            self.mode = mode
            self._error = None
            self._notice = "実機は未接続のため、物理LEDの消灯は確認できていません。" if unknown else None
            if mode == "real":
                return self.connect()
            return self.snapshot()

    def close(self):
        with self._lock:
            if self.mode == "real" and self._serial is not None:
                try:
                    self._exchange("0")
                except ControllerError:
                    pass
            self._drop()

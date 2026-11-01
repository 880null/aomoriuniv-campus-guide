"""OS別の起動ファイルを実行してHTTPと任意のブラウザを検証する。実機には接続しない。"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


def request(base, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if body is None else {"Content-Type": "application/json"}
    try:
        with urlopen(Request(base + path, data=body, headers=headers), timeout=5) as response:
            raw = response.read()
            content_type = response.headers.get_content_type()
            return response.status, json.loads(raw) if content_type == "application/json" else raw
    except HTTPError as error:
        return error.code, json.loads(error.read())


def unused_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def launch_command(directory, args):
    launcher = directory / ("start.bat" if os.name == "nt" else "start.command")
    command = [str(launcher), *args]
    if os.name == "nt":
        return (subprocess.list2cmdline([os.environ.get("COMSPEC", "cmd.exe")])
                + ' /d /s /c "' + subprocess.list2cmdline(command) + '"')
    if not os.access(launcher, os.X_OK):
        raise RuntimeError("start.commandの実行権限がありません。")
    return ["/bin/zsh", str(launcher), *args]


def launch_environment(offline=False):
    environment = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    environment["PY_PYTHON3"] = f"{sys.version_info.major}.{sys.version_info.minor}"
    if offline:
        environment["PIP_NO_INDEX"] = "1"
    return environment


@contextmanager
def running_app(directory, logs, *, simulation, offline=False):
    port = unused_port()
    base = f"http://127.0.0.1:{port}"
    # 存在しないポートを明示し、検証中に利用者の実機を自動選択しない。
    missing = "COM9999" if os.name == "nt" else "/dev/campus-guide-test-missing"
    args = ["--no-browser", "--port", str(port), "--serial-port", missing]
    if simulation:
        args.append("--simulate")
    command = launch_command(directory, args)
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    environment = launch_environment(offline)
    # 常駐プロセスの出力はローカル一時領域へ。同期中のクラウドフォルダーのFDを子へ渡さない。
    local_logs = directory.parent / logs.name
    with local_logs.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=directory.parent, env=environment,
                                   stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, **options)
        try:
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"起動ファイルが終了しました: {process.returncode}\n{local_logs.read_text(encoding='utf-8')}")
                # 初回のvenv/pip準備が完了するまでは、サーバーへの照会を始めない。
                if base in local_logs.read_text(encoding="utf-8", errors="replace"):
                    try:
                        if request(base, "/api/status")[0] == 200:
                            break
                    except (URLError, TimeoutError):
                        pass
                if time.monotonic() > deadline:
                    raise TimeoutError(f"起動待ちがタイムアウトしました: {logs}")
                time.sleep(0.1)
            yield base
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    # CIに対話コンソールはないため、子を含めて終了する。Ctrl+C確認とは区別する。
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    request(base, "/api/status")
                except (URLError, TimeoutError):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("検証用サーバーが終了していません。")
            shutil.copy2(local_logs, logs)


def check_http(base, simulation):
    for path in ("/", "/static/style.css", "/static/app.js", "/static/campus-map.png"):
        status, content = request(base, path)
        assert status == 200 and content, path
    for key in "ABCDEFGHIJK":
        status, content = request(base, f"/static/floorplans/{key}.pdf")
        assert status == 200 and content.startswith(b"%PDF"), key
    buildings = request(base, "/api/buildings")[1]
    assert len(buildings["buildings"]) == 14
    assert len(request(base, "/api/map")[1]["markers"]) == 13
    rooms = request(base, "/api/rooms?q=5301")[1]["rooms"]
    assert (rooms[0]["building_id"], rooms[0]["floor"]) == ("D", "3階")
    assert request(base, "/api/rooms?q=9999")[1]["total"] == 0
    state = request(base, "/api/status")[1]["status"]
    assert state["mode"] == ("simulation" if simulation else "real")
    assert not state["connected"]
    if simulation:
        for key in "ABCDEFH":
            status, result = request(base, "/api/select", {"building_id": key})
            assert status == 200 and result["status"]["active_building"] == key
        assert request(base, "/api/off", {})[1]["status"]["led_state"] == "off"
    else:
        status, result = request(base, "/api/select", {"building_id": "A"})
        assert status == 503 and result["status"]["led_state"] == "unknown"


def check_browser(base, browser_name, destination):
    from playwright.sync_api import expect, sync_playwright

    request(base, "/api/mode", {"mode": "simulation"})
    errors = []
    with sync_playwright() as playwright:
        engine = playwright.chromium if browser_name == "msedge" else getattr(playwright, browser_name)
        options = {"channel": "msedge"} if browser_name == "msedge" else {}
        browser = engine.launch(**options)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            expect(page.locator("#connection-badge")).to_have_text("シミュレーション")
            expect(page.locator(".building-button")).to_have_count(14)
            expect(page.locator(".map-marker")).to_have_count(13)
            expect(page.locator("#map-image")).to_be_visible()
            assert page.locator("#map-image").evaluate("image => image.naturalWidth > 0")
            assert page.locator(".guide-layout").evaluate("element => getComputedStyle(element).display") == "grid"

            def idle():
                expect(page.locator("main")).to_have_attribute("aria-busy", "false")

            def search(query):
                page.locator("#search").fill(query)
                page.locator("#search-form").press("Enter")
                idle()

            for key in "ABCDEFH":
                page.locator(f'.map-marker[data-building="{key}"]').click()
                idle()
                assert request(base, "/api/status")[1]["status"]["active_building"] == key
            search("５３０１教室")
            expect(page.locator("#search-room-list .room-button")).to_have_count(1)
            page.locator("#search-room-list .room-button").click()
            idle()
            expect(page.locator("#destination-name")).to_contain_text("5301")
            expect(page.locator("#destination-detail")).to_contain_text("5号館 · 3階")
            expect(page.locator("#destination-plan")).to_have_attribute("href", "/static/floorplans/D.pdf#page=2")
            expect(page.locator("#led-indicator")).to_have_text("模擬点灯中")
            page.screenshot(path=str(destination / f"{browser_name}-desktop.png"), full_page=True)

            page.locator('.map-marker[data-building="G"]').click()
            idle()
            expect(page.locator("#led-indicator")).to_have_text("画面案内のみ")
            assert request(base, "/api/status")[1]["status"]["led_state"] == "off"
            page.locator("#floor-filter").select_option("2階")
            expect(page.locator("#building-room-list .room-button")).to_have_count(2)
            search("9999")
            expect(page.locator("#empty-results")).to_be_visible()
            search("保健室")
            page.locator("#search-room-list .room-button").click()
            idle()
            expect(page.locator("#destination-detail")).to_contain_text("7号館 · 1階")

            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "横方向にはみ出しています。"
            page.screenshot(path=str(destination / f"{browser_name}-mobile.png"), full_page=True)
            page.locator("#settings summary").click()
            # モード切替中はAPIの応答まで旧状態を描画するため、完了後の状態を検査する。
            page.locator('input[name="mode"][value="real"]').click()
            idle()
            expect(page.locator("#connection-badge")).to_have_text("Arduino 未接続")
            search("保健室")
            page.locator("#search-room-list .room-button").click()
            idle()
            expect(page.locator("#destination-detail")).to_contain_text("7号館 · 1階")
            expect(page.locator("#led-indicator")).to_have_text("LED状態不明")
            expect(page.locator("#error")).to_be_visible()
            page.screenshot(path=str(destination / f"{browser_name}-disconnected.png"), full_page=True)
            assert not errors, errors
        finally:
            browser.close()
    return {"browser": browser_name, "result": "passed", "uncaught_errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="append", default=[], choices=["chromium", "webkit", "firefox", "msedge"])
    parser.add_argument("--report", type=Path, default=ROOT / "validation-results/runtime.json")
    args = parser.parse_args()
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"os": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": [], "result": "failed",
              "limits": ["Arduino実機・配線は未検証", "Finder/Explorerのダブルクリックは未検証",
                         "既定ブラウザの自動起動は未検証（--no-browserで検査）"]}
    temporary = tempfile.mkdtemp(prefix="campus-verify-")
    try:
        directory = Path(temporary) / "青森 大学 キャンパスガイド"
        directory.mkdir()
        for name in ("backend", "frontend", "data", "scripts"):
            shutil.copytree(ROOT / name, directory / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("start.command", "start.bat", "requirements.txt"):
            shutil.copy2(ROOT / name, directory / name)
        # パッケージ初回準備と、常駐サーバーの起動を別々に検査・記録する。
        prepared = subprocess.run(launch_command(directory, ["--help"]), cwd=directory.parent,
                                  env=launch_environment(), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (report_path.parent / "installation.log").write_bytes(prepared.stdout)
        if prepared.returncode:
            raise RuntimeError(f"初回環境準備に失敗しました: {prepared.returncode}")
        report["checks"].append({"case": "fresh environment preparation through OS launcher", "result": "passed"})
        with running_app(directory, report_path.parent / "first-start.log", simulation=True) as base:
            check_http(base, True)
            report["checks"].append({"case": "Japanese and spaced directory / HTTP / simulation", "result": "passed"})
            python = directory / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            actual = subprocess.check_output([str(python), "-c", "import platform; print(platform.python_version())"], text=True).strip()
            report["app_python"] = actual
            assert actual.split(".")[:2] == platform.python_version().split(".")[:2], (actual, platform.python_version())
            for browser in args.browser:
                report["checks"].append(check_browser(base, browser, report_path.parent))
        with running_app(directory, report_path.parent / "offline-start.log", simulation=False, offline=True) as base:
            check_http(base, False)
            report["checks"].append({"case": "offline restart / disconnected real mode / HTTP available", "result": "passed"})
        report["shutdown"] = "process-tree termination" if os.name == "nt" else "SIGINT / Ctrl+C equivalent"
        report["result"] = "passed"
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if report["result"] == "passed":
            shutil.rmtree(temporary)
        else:
            report["debug_workspace"] = temporary
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

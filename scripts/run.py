"""Arduino接続・HTTP起動・準備完了後のブラウザ起動。"""

import argparse
import logging
import os
import threading
import time
from urllib.request import urlopen
import webbrowser

from waitress import create_server

from backend.app import create_app
from backend.controller import ControllerError, LedController


def open_when_ready(url):
    # 固定の待ち時間だけに頼らず、実際にHTTP応答を確認する。
    for _ in range(30):
        try:
            with urlopen(url + "/api/status", timeout=1) as response:
                if response.status == 200:
                    if not webbrowser.open(url):
                        logging.warning("ブラウザを開けませんでした。%s を手動で開いてください。", url)
                    return
        except OSError:
            time.sleep(0.2)
    logging.warning("自動表示できませんでした。%s を手動で開いてください。", url)


def main():
    parser = argparse.ArgumentParser(description="青森大学インタラクティブキャンパスガイド")
    parser.add_argument("--simulate", action="store_true", help="USBに接続せずシミュレーションで起動")
    parser.add_argument("--no-browser", action="store_true", help="ブラウザを自動起動しない")
    parser.add_argument("--serial-port", default=os.environ.get("CAMPUS_SERIAL_PORT"), help="COM3等のUSBポート")
    parser.add_argument("--port", type=int, default=5050, help="ローカルHTTPポート（標準5050）")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--portは1〜65535で指定してください。")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    controller = LedController("simulation" if args.simulate else "real", args.serial_port)
    server = None
    try:
        app = create_app(controller)
        # ポート競合を先に検出し、起動に失敗する場合はUSBへ接続しない。
        server = create_server(app, host="127.0.0.1", port=args.port, threads=4)
        if not args.simulate:
            try:
                controller.connect()
            except ControllerError as exc:
                logging.warning("%s（Webアプリは起動します）", exc)
        url = f"http://127.0.0.1:{args.port}"
        print(f"\n青森大学キャンパスガイド: {url}\n終了するにはこの画面で Ctrl+C を押してください。\n", flush=True)
        if not args.no_browser:
            threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
        server.run()
    except KeyboardInterrupt:
        print("\n終了します。LEDの消灯を試みます。", flush=True)
    except (OSError, ValueError) as exc:
        logging.error("起動できません: %s（ポート競合時は --port 5051 を指定）", exc)
        return 1
    finally:
        controller.close()
        if server is not None:
            server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

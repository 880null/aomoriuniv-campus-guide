"""画面配信とJSON API。USB通信の詳細はコントローラーへ分離する。"""

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from backend.catalog import Catalog
from backend.controller import ControllerError, LedController

ROOT = Path(__file__).resolve().parent.parent


def create_app(controller=None, data_directory=None):
    app = Flask(__name__, static_folder=str(ROOT / "frontend/static"), static_url_path="/static")
    app.config.update(MAX_CONTENT_LENGTH=4096, TRUSTED_HOSTS=["localhost", "127.0.0.1"])
    catalog = Catalog(data_directory or ROOT / "data")
    leds = controller or LedController()
    app.extensions["led_controller"] = leds

    @app.before_request
    def local_requests_only():
        # ローカル機器の制御を、外部ページからのPOSTで実行させない。
        if request.method == "POST":
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return jsonify(error="別サイトからの制御は許可されていません。"), 403
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error="別オリジンからの制御は許可されていません。"), 403
            if not request.is_json:
                return jsonify(error="application/jsonで送信してください。"), 415

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError("JSONオブジェクトを送信してください。")
        return value

    @app.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(ControllerError)
    def unavailable(exc):
        return jsonify(error=str(exc), status=leds.snapshot()), 503

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    @app.get("/")
    def index():
        return send_from_directory(ROOT / "frontend", "index.html")

    @app.get("/api/buildings")
    def buildings():
        query = request.args.get("q", "")
        if len(query) > 80:
            raise ValueError("検索は80文字以内で入力してください。")
        results, message = catalog.search(query)
        return jsonify(buildings=results, message=message, verified_room_count=len(catalog.rooms))

    @app.get("/api/map")
    def campus_map():
        return jsonify(catalog.map)

    @app.get("/api/status")
    def status():
        return jsonify(status=leds.status())

    @app.get("/api/ports")
    def ports():
        return jsonify(ports=leds.ports())

    @app.post("/api/select")
    def select():
        key = body().get("building_id")
        if not isinstance(key, str):
            raise ValueError("building_idは文字列が必要です。")
        if key not in catalog.by_id:
            return jsonify(error="この建物はLED案内の対象外です。"), 404
        return jsonify(status=leds.select(key))

    @app.post("/api/off")
    def off():
        body()
        return jsonify(status=leds.select("0"))

    @app.post("/api/connection")
    def connection():
        port = body().get("port")
        if port is not None and (not isinstance(port, str) or not port.strip()):
            raise ValueError("portは空でない文字列が必要です。")
        return jsonify(status=leds.connect(port))

    @app.post("/api/mode")
    def mode():
        value = body().get("mode")
        if not isinstance(value, str):
            raise ValueError("modeは文字列が必要です。")
        return jsonify(status=leds.set_mode(value))

    return app

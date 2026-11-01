"""施設と確認済み教室の読み込み・検索。"""

import json
import math
import unicodedata
from datetime import date
from pathlib import Path

# 実装担当者の共有とユーザー指定に基づく設定。NoneはLED未実装の施設。
PIN_MAP = {"A": 2, "B": 3, "C": None, "D": 4, "E": 5, "F": 6, "H": 7}


def normalize(value: str) -> str:
    """全角英数字と空白の違いを吸収する。番号から建物は推測しない。"""
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def room_key(value: str) -> str:
    return normalize(value).removesuffix("教室")


class Catalog:
    def __init__(self, directory: Path):
        def read(name):
            return json.loads((directory / name).read_text(encoding="utf-8"))

        self.buildings = read("buildings.json")
        if not isinstance(self.buildings, list):
            raise ValueError("buildings.jsonは配列が必要です。")
        self.by_id = {}
        for building in self.buildings:
            key = building["id"]
            if key not in PIN_MAP or key in self.by_id or building["pin"] != PIN_MAP[key]:
                raise ValueError("施設のID・ピンの対応が仕様と異なります。")
            if not isinstance(building["name"], str) or not building["name"].strip():
                raise ValueError("建物名が必要です。")
            if not isinstance(building["aliases"], list) or not all(
                isinstance(alias, str) and alias.strip() for alias in building["aliases"]
            ):
                raise ValueError("検索用別名は文字列の配列にしてください。")
            self.by_id[key] = building
        if set(self.by_id) != set(PIN_MAP):
            raise ValueError("7施設すべての登録が必要です。")

        self.rooms = {}
        for room in read("rooms.json")["rooms"]:
            if not isinstance(room["number"], str) or not room_key(room["number"]):
                raise ValueError("教室番号は空でない文字列が必要です。")
            key = room_key(room["number"])
            if key in self.rooms or room["building_id"] not in self.by_id:
                raise ValueError("教室番号の重複、または未知の建物があります。")
            if not isinstance(room["source"], str) or not room["source"].strip():
                raise ValueError("教室には確認元sourceが必要です。")
            verified = date.fromisoformat(room["verified_on"])
            if verified > date.today():
                raise ValueError("教室の確認日を未来にできません。")
            self.rooms[key] = room

        self.map = read("map.json")
        markers = self.map["markers"]
        if len(markers) != 7 or {m["id"] for m in markers} != set(PIN_MAP):
            raise ValueError("地図マーカーは7施設と一致させてください。")
        for marker in markers:
            if not all(type(marker[k]) in (int, float) and math.isfinite(marker[k])
                       and 0 <= marker[k] <= 100 for k in ("x", "y")):
                raise ValueError("マーカー座標は0〜100の数値にしてください。")

    def search(self, query: str):
        key = normalize(query)
        if not key:
            wired_count = sum(b["pin"] is not None for b in self.buildings)
            return self.buildings, f"7施設を表示しています。実機LEDは設定済みの{wired_count}施設に対応しています。"
        room = self.rooms.get(room_key(query))
        if room:
            return [self.by_id[room["building_id"]]], f"確認済み教室「{room['number']}」の建物です。"
        results = [b for b in self.buildings if key == normalize(b["id"]) or any(
            key in normalize(name) for name in [b["name"], *b["aliases"]]
        )]
        if results:
            return results, f"{len(results)}件の施設が見つかりました。"
        return [], "該当する施設がありません。教室情報は未登録の場合があります。建物名で検索してください。"

"""公式案内図で確認した施設・教室の検証と検索。USB用の配線とは分けて扱う。"""

import json
import math
import re
import unicodedata
from datetime import date
from pathlib import Path

# 画面だけで案内する建物を追加しても、ハードウェアの通信契約は変更しない。
PIN_MAP = {"A": 2, "B": 3, "C": None, "D": 4, "E": 5, "F": 6, "H": 7}


def normalize(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def room_key(value: str) -> str:
    return normalize(value).removesuffix("教室").removesuffix("号室")


class Catalog:
    def __init__(self, directory: Path):
        def read(name):
            return json.loads((directory / name).read_text(encoding="utf-8"))

        self.sources = {s["building_id"]: s for s in read("floorplan_sources.json")["sources"]}
        self.buildings = read("buildings.json")
        self.by_id = {}
        for building in self.buildings:
            key = building["id"]
            if not isinstance(key, str) or key in self.by_id or building["pin"] != PIN_MAP.get(key):
                raise ValueError("施設のID・ピンの対応が仕様と異なります。")
            if not isinstance(building["name"], str) or not building["name"].strip():
                raise ValueError("建物名が必要です。")
            if not isinstance(building["aliases"], list) or not all(
                isinstance(alias, str) and alias.strip() for alias in building["aliases"]
            ):
                raise ValueError("検索用別名は文字列の配列にしてください。")
            source = self.sources[building["source_id"]]
            building["floorplan"] = {"label": source["label"], "url": source["url"],
                                     "local_url": f"/static/floorplans/{source['building_id']}.pdf"}
            building["simulation_led"] = key in PIN_MAP
            self.by_id[key] = building
        if not set(PIN_MAP).issubset(self.by_id):
            raise ValueError("LED制御に関係する7施設の登録が必要です。")

        self.rooms, self.destinations, self.by_room_id = {}, [], {}
        for room in read("rooms.json")["rooms"]:
            number = room["number"]
            if number is not None and (not isinstance(number, str) or not room_key(number)):
                raise ValueError("教室番号は空でない文字列、または未記載を示すnullが必要です。")
            if room["building_id"] is not None and room["building_id"] not in self.by_id:
                raise ValueError("未知の建物があります。")
            if not isinstance(room["source"], str) or not room["source"].strip():
                raise ValueError("教室には確認元sourceが必要です。")
            source = self.sources.get(room["source_id"])
            if not source or room["source"] != source["url"]:
                raise ValueError("sourceは原図一覧と一致させてください。")
            if type(room["source_page"]) is not int or not 1 <= room["source_page"] <= source["pages"]:
                raise ValueError("確認元ページが不正です。")
            if date.fromisoformat(room["verified_on"]) > date.today():
                raise ValueError("教室の確認日を未来にできません。")
            if not isinstance(room["id"], str) or not room["id"] or room["id"] in self.by_room_id:
                raise ValueError("案内地点IDが空、または重複しています。")
            if not isinstance(room["name"], str) or not room["name"].strip():
                raise ValueError("案内地点名が必要です。")
            if room["floor"] is not None and (not isinstance(room["floor"], str) or not room["floor"].strip()):
                raise ValueError("階は文字列、またはnullが必要です。")
            if (room["building_id"] is None or room["floor"] is None) and not room["location_note"]:
                raise ValueError("棟・階の未確認箇所には理由を記載してください。")
            if number:
                key = room_key(number)
                if key in self.rooms:
                    raise ValueError("教室番号が重複しています。")
                self.rooms[key] = room
            self.destinations.append(room)
            self.by_room_id[room["id"]] = room
        for building in self.buildings:
            entries = [r for r in self.destinations if r["building_id"] == building["id"]]
            building["destination_count"] = len(entries)
            building["floors"] = list(dict.fromkeys(r["floor"] for r in entries if r["floor"]))

        self.map = read("map.json")
        keys = [m["id"] for m in self.map["markers"]]
        if len(keys) != len(set(keys)) or not set(keys).issubset(self.by_id) or not set(PIN_MAP).issubset(keys):
            raise ValueError("地図マーカーは登録済み施設と一致させてください。")
        for marker in self.map["markers"]:
            if not all(type(marker[k]) in (int, float) and math.isfinite(marker[k])
                       and 0 <= marker[k] <= 100 for k in ("x", "y")):
                raise ValueError("マーカー座標は0〜100の数値にしてください。")

    def search_destinations(self, query="", building_id=None, floor=None):
        key = normalize(query)
        symbol = next((b["id"] for b in self.buildings if normalize(b["id"]) == key), None)
        if symbol:
            return [r for r in self.destinations if r["building_id"] == symbol
                    and (not building_id or building_id == symbol)
                    and (not floor or (r["floor"] or "未記載") == floor)]
        # 数字単独は完全一致のみ。未登録番号の先頭桁から建物を推測しない。
        exact = self.rooms.get(room_key(query)) if key else None
        if exact:
            candidates = [exact]
        elif room_key(query).isdecimal():
            candidates = []
        else:
            candidates = self.destinations
        results = []
        for room in candidates:
            if building_id and room["building_id"] != building_id:
                continue
            if floor and (room["floor"] or "未記載") != floor:
                continue
            if not key or exact:
                results.append(room)
                continue
            building = self.by_id.get(room["building_id"], {})
            labels = [room["name"], room["number"] or "", *room["aliases"]]
            locations = [building.get("name", ""), *building.get("aliases", []), room["area"], room["floor"] or ""]
            haystack = normalize(" ".join([*labels, *locations]))
            combinations = [normalize(a + b) for a in locations for b in labels]
            # 「３ 号館」は1語、「5号館 トイレ」は2語として扱う。
            words = re.sub(r"(\d)\s+(?=号館|階|教室|号室)", r"\1", unicodedata.normalize("NFKC", query)).split()
            if key in haystack or any(key in c for c in combinations) or (
                len(words) > 1 and all(normalize(word) in haystack for word in words)
            ):
                results.append(room)
        return results

    def search(self, query: str):
        key = normalize(query)
        if not key:
            return self.buildings, f"{len(self.buildings)}施設・{len(self.destinations)}地点を案内します。実機LEDは6施設です。"
        destinations = self.search_destinations(query)
        symbol = self.by_id.get(key.upper())
        if symbol:
            return [symbol], f"建物1件・教室／施設{len(destinations)}件が見つかりました。"
        room_buildings = {room["building_id"] for room in destinations}
        results = [b for b in self.buildings if b["id"] in room_buildings or key == normalize(b["id"]) or any(
            key in normalize(name) for name in [b["name"], *b["aliases"]]
        )]
        if results or destinations:
            return results, f"建物{len(results)}件・教室／施設{len(destinations)}件が見つかりました。"
        return [], "該当する施設がありません。教室情報は未登録の場合があります。番号や施設名を確認してください。"

"""目視転記JSONから検索データを生成する。python scripts/build_room_catalog.py [--check]"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(directory=ROOT / "data"):
    sources = json.loads((directory / "floorplan_sources.json").read_text(encoding="utf-8"))["sources"]
    rooms, coverage = [], []
    for source in sources:
        key = source["building_id"]
        if hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"{key}: 原図のハッシュが一致しません。")
        document = json.loads((directory / "extraction" / f"{key}.json").read_text(encoding="utf-8"))
        if document["source_id"] != key or document["reviewed_pages"] != list(range(1, source["pages"] + 1)):
            raise ValueError(f"{key}: 未確認ページがあります。")
        seen = Counter()
        start = len(rooms)
        for index, group in enumerate(document["groups"], 1):
            page = group["page"]
            if type(page) is not int or not 1 <= page <= source["pages"]:
                raise ValueError(f"{key}: ページ番号が不正です。")
            for item in group["entries"]:
                # 同名の無番号室は、元図の区画順と位置補足で区別する。
                base = f"{key}-p{page}-g{index}"
                seen[base] += 1
                rooms.append({
                    "id": f"{base}-r{seen[base]}", "number": item["number"],
                    "name": item["name"], "building_id": group["building_id"],
                    "floor": item.get("floor_override", group["floor"]), "area": group["area"],
                    "category": item["category"], "aliases": item["aliases"],
                    "location_hint": item.get("location_hint", ""), "location_note": group["note"],
                    "source_id": key, "source": source["url"], "source_page": page,
                    "source_label": source["label"], "verified_on": source["retrieved_on"],
                    "local_plan": f"/static/floorplans/{key}.pdf#page={page}",
                })
        entries = rooms[start:]
        coverage.append({"source_id": key, "pages": document["reviewed_pages"], "destinations": len(entries),
                         "numbered_rooms": sum(r["number"] is not None for r in entries),
                         "excluded_labels": document["excluded_labels"]})
    numbers = [r["number"] for r in rooms if r["number"]]
    if len(numbers) != len(set(numbers)):
        raise ValueError("番号が重複しています。原図を確認してください。")
    return {"note": "青森大学公式の全11案内図・15ページから目視転記。現地未照合。棟・階・番号の未記載部分は推定しない。",
            "coverage": coverage, "rooms": rooms}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="再生成結果と原図ハッシュを検査する")
    args = parser.parse_args()
    result = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    target = ROOT / "data/rooms.json"
    if args.check:
        if target.read_text(encoding="utf-8") != result:
            raise SystemExit("rooms.jsonが転記元と一致しません。再生成してください。")
    else:
        target.write_text(result, encoding="utf-8")
    print(f"案内地点 {len(json.loads(result)['rooms'])}件 / 11案内図・15ページ")

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from backend.app import ROOT
from backend.catalog import Catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT / "data")

    def test_seven_buildings_and_pins(self):
        self.assertEqual({b["id"]: b["pin"] for b in self.catalog.buildings},
                         dict(A=2, B=3, C=4, D=5, E=6, F=7, H=8))

    def test_official_rooms_are_empty(self):
        self.assertEqual(self.catalog.rooms, {})

    def test_search_normalizes_fullwidth_and_spaces(self):
        self.assertEqual(self.catalog.search(" ３ 号館 ")[0][0]["id"], "B")
        self.assertEqual(self.catalog.search("ｈ")[0][0]["id"], "H")

    def test_search_aliases(self):
        self.assertEqual(self.catalog.search("食堂")[0][0]["id"], "H")

    def test_unknown_room_is_not_guessed_from_prefix(self):
        buildings, message = self.catalog.search("123教室")
        self.assertEqual(buildings, [])
        self.assertIn("未登録", message)

    def test_out_of_scope_building(self):
        self.assertEqual(self.catalog.search("2号館")[0], [])

    def temporary_catalog(self, rooms):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for path in (ROOT / "data").glob("*.json"):
            shutil.copy(path, directory)
        (directory / "rooms.json").write_text(json.dumps({"rooms": rooms}), encoding="utf-8")
        return directory

    def test_confirmed_room_lookup_only_in_temporary_fixture(self):
        # 実在の情報ではない。正式JSONへは登録しない。
        room = dict(number="TEST-101", building_id="A", source="テスト専用の架空資料", verified_on="2020-01-01")
        catalog = Catalog(self.temporary_catalog([room]))
        self.assertEqual(catalog.search("ＴＥＳＴ－１０１教室")[0][0]["id"], "A")

    def test_room_without_source_is_rejected(self):
        room = dict(number="TEST-101", building_id="A", source="", verified_on="2020-01-01")
        with self.assertRaisesRegex(ValueError, "source"):
            Catalog(self.temporary_catalog([room]))

    def test_duplicate_rooms_after_normalization_are_rejected(self):
        room = dict(number="TEST-101", building_id="A", source="テスト資料", verified_on="2020-01-01")
        with self.assertRaisesRegex(ValueError, "重複"):
            Catalog(self.temporary_catalog([room, {**room, "number": "ＴＥＳＴ－１０１"}]))

    def test_invalid_marker_is_rejected(self):
        directory = self.temporary_catalog([])
        data = json.loads((directory / "map.json").read_text())
        data["markers"][0]["x"] = 101
        (directory / "map.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "座標"):
            Catalog(directory)

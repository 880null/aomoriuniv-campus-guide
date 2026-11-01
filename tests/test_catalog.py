import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from backend.app import ROOT
from backend.catalog import Catalog, PIN_MAP
from scripts.build_room_catalog import build


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT / 'data')

    def test_buildings_and_hardware_remain_separate(self):
        self.assertEqual(len(self.catalog.buildings), 14)
        self.assertEqual({key:self.catalog.by_id[key]['pin'] for key in PIN_MAP}, PIN_MAP)
        for key in 'GIJKNQT':
            self.assertIsNone(self.catalog.by_id[key]['pin'])
            self.assertFalse(self.catalog.by_id[key]['simulation_led'])

    def test_all_sources_pages_and_generated_data_match(self):
        result = build()
        self.assertEqual(result, json.loads((ROOT / 'data/rooms.json').read_text(encoding='utf-8')))
        self.assertEqual({r['source_id'] for r in result['coverage']}, set('ABCDEFGHIJK'))
        self.assertEqual(sum(len(r['pages']) for r in result['coverage']), 15)
        self.assertEqual(len(self.catalog.destinations), 369)
        self.assertEqual(len(self.catalog.rooms), 155)

    def test_every_number_can_be_found_exactly(self):
        for number, room in self.catalog.rooms.items():
            with self.subTest(number=number):
                self.assertEqual(self.catalog.search_destinations(number), [room])
                self.assertEqual(self.catalog.search_destinations(number+'教室'), [room])

    def test_every_destination_remains_available_by_name_and_id(self):
        for room in self.catalog.destinations:
            with self.subTest(room=room['id']):
                self.assertEqual(self.catalog.by_room_id[room['id']], room)
                self.assertIn(room, self.catalog.search_destinations(room['name']))

    def test_floor_is_not_inferred_from_number(self):
        for number in ('340','350'):
            self.assertEqual(self.catalog.rooms[number]['floor'], '2階')
        self.assertEqual(self.catalog.rooms['5301']['floor'], '3階')
        self.assertEqual(self.catalog.rooms['775']['floor'], '7階')
        self.assertEqual(self.catalog.rooms['761']['name'], '761')
        self.assertEqual(self.catalog.search_destinations('5608'), [])
        self.assertEqual(self.catalog.search_destinations('713'), [])

    def test_search_normalization_aliases_and_combined_query(self):
        for symbol in 'ABCDEFGHIJK':
            self.assertEqual([b['id'] for b in self.catalog.search(symbol)[0]], [symbol])
        self.assertEqual(self.catalog.search(' ３ 号館 ')[0][0]['id'], 'B')
        self.assertEqual(self.catalog.search('ｈ')[0][0]['id'], 'H')
        self.assertEqual(self.catalog.search('食堂')[0][0]['id'], 'H')
        self.assertEqual(self.catalog.search_destinations('５３０１教室')[0]['number'], '5301')
        toilets = self.catalog.search_destinations('5号館 トイレ')
        self.assertEqual(len(toilets),12)
        self.assertTrue(all(room['building_id']=='D' for room in toilets))

    def test_same_name_rooms_are_not_overwritten(self):
        rooms = self.catalog.search_destinations('実習室', 'B', '1階')
        self.assertEqual(len(rooms),4)
        self.assertEqual(len({room['location_hint'] for room in rooms}),4)
        self.assertEqual(len({room['id'] for room in rooms}),4)

    def test_unknown_room_is_not_guessed_from_prefix(self):
        buildings, message = self.catalog.search('123教室')
        self.assertEqual(buildings, [])
        self.assertIn('未登録', message)
        self.assertEqual(self.catalog.search_destinations('101'), [])

    def test_unknown_locations_are_explicit(self):
        rooms = [r for r in self.catalog.destinations if r['building_id'] is None or r['floor'] is None]
        self.assertGreater(len(rooms),0)
        self.assertTrue(all(room['location_note'] for room in rooms))
        self.assertEqual(self.catalog.search_destinations('集いのスペース')[0]['floor'], None)
        self.assertEqual(self.catalog.by_id['T']['destination_count'],0)
        self.assertNotIn('T',{m['id'] for m in self.catalog.map['markers']})

    def temporary_catalog(self, rooms):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for path in (ROOT / 'data').glob('*.json'):
            shutil.copy(path, directory)
        (directory / 'rooms.json').write_text(json.dumps({'rooms':rooms}),encoding='utf-8')
        return directory

    def fixture(self):
        # 架空情報は一時ディレクトリだけで使う。正式データには追加しない。
        room = copy.deepcopy(self.catalog.rooms['311'])
        room.update(id='test-room', number='TEST-101', name='テスト専用の教室')
        return room

    def test_temporary_room_lookup(self):
        catalog = Catalog(self.temporary_catalog([self.fixture()]))
        self.assertEqual(catalog.search('ＴＥＳＴ－１０１教室')[0][0]['id'],'B')

    def test_room_without_source_is_rejected(self):
        room = self.fixture(); room['source']=''
        with self.assertRaisesRegex(ValueError,'source'):
            Catalog(self.temporary_catalog([room]))

    def test_duplicate_normalized_number_is_rejected(self):
        room = self.fixture()
        with self.assertRaisesRegex(ValueError,'重複'):
            Catalog(self.temporary_catalog([room,{**room,'id':'another','number':'ＴＥＳＴ－１０１'}]))

    def test_source_page_and_future_date_are_rejected(self):
        for fields in ({'source_page':99},{'verified_on':'2999-01-01'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                Catalog(self.temporary_catalog([{**self.fixture(),**fields}]))

    def test_invalid_marker_is_rejected(self):
        directory=self.temporary_catalog([])
        data=json.loads((directory/'map.json').read_text(encoding='utf-8'))
        data['markers'][0]['x']=101
        (directory/'map.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'座標'):
            Catalog(directory)

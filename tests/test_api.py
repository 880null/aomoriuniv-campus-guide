import unittest

from backend.app import create_app
from backend.controller import LedController


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.controller = LedController("simulation", ports_provider=lambda: [])
        self.app = create_app(self.controller)
        self.app.testing = True
        self.client = self.app.test_client()

    def test_page_and_local_map(self):
        with self.client.get("/") as page:
            self.assertEqual(page.status_code, 200)
        image = self.client.get("/static/campus-map.png")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/png")
        image.close()

    def test_buildings_and_map(self):
        buildings = self.client.get("/api/buildings").json
        self.assertEqual(len(buildings["buildings"]), 14)
        self.assertEqual(buildings["verified_room_count"], 155)
        self.assertEqual(len(self.client.get("/api/map").json["markers"]), 13)

    def test_search_and_unknown_room(self):
        result = self.client.get("/api/buildings", query_string={"q": "６号館"}).json
        self.assertEqual(result["buildings"][0]["id"], "E")
        self.assertEqual(self.client.get("/api/buildings?q=101").json["buildings"], [])

    def test_select_all_buildings_and_off(self):
        for key in "ABCDEFH":
            result = self.client.post("/api/select", json={"building_id": key})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["status"]["active_building"], key)
        self.assertEqual(self.client.post("/api/off", json={}).json["status"]["led_state"], "off")

    def test_out_of_scope_or_invalid_selection(self):
        for key in ("0", "Z", "AA"):
            self.assertEqual(self.client.post("/api/select", json={"building_id": key}).status_code, 404)
        for value in ({}, {"building_id": []}, [], None, {"building_id": 1}):
            self.assertEqual(self.client.post("/api/select", json=value).status_code in (400, 415), True)

    def test_unwired_buildings_cannot_send_commands(self):
        self.client.post("/api/select", json={"building_id":"A"})
        for key in "GIJKNQT":
            result=self.client.post("/api/select", json={"building_id":key})
            self.assertEqual(result.status_code,400)
            self.assertEqual(self.controller.snapshot()["active_building"],"A")

    def test_all_rooms_and_floor_filters(self):
        self.assertEqual(self.client.get("/api/rooms").json["total"],369)
        result=self.client.get("/api/rooms",query_string={"q":"保健室"}).json
        room=result["rooms"][0]
        self.assertEqual((room["number"],room["building_id"],room["floor"]),("711","F","1階"))
        detail=self.client.get("/api/rooms/"+room["id"]).json
        self.assertEqual(detail["room"],room)
        self.assertEqual(detail["building"]["pin"],6)
        self.assertEqual(self.client.get("/api/rooms/unknown").status_code,404)
        self.assertEqual(self.client.get("/api/rooms?building_id=unknown").status_code,404)
        rooms=self.client.get("/api/rooms?building_id=D&floor=6階").json["rooms"]
        self.assertTrue(rooms)
        self.assertTrue(all(r["building_id"]=="D" and r["floor"]=="6階" for r in rooms))
        self.assertEqual(self.client.get("/api/rooms?q="+"x"*81).status_code,400)

    def test_every_local_floorplan_is_available_offline(self):
        for key in "ABCDEFGHIJK":
            with self.subTest(key=key), self.client.get(f"/static/floorplans/{key}.pdf") as response:
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.mimetype,"application/pdf")
                self.assertTrue(response.data.startswith(b"%PDF"))

    def test_disconnected_real_mode_returns_503(self):
        result = self.client.post("/api/mode", json={"mode": "real"})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json["status"]["led_state"], "unknown")
        with self.client.get("/") as page:
            self.assertEqual(page.status_code, 200)
        result = self.client.post("/api/select", json={"building_id": "A"})
        self.assertEqual(result.status_code, 503)
        self.assertIsNone(result.json["status"]["active_building"])

    def test_invalid_mode_and_port_type(self):
        for mode in ("bad", [], None):
            self.assertEqual(self.client.post("/api/mode", json={"mode": mode}).status_code, 400)
        self.assertEqual(self.client.post("/api/connection", json={"port": []}).status_code, 400)

    def test_rejects_cross_origin_control(self):
        result = self.client.post("/api/off", json={}, headers={"Origin": "https://example.com"})
        self.assertEqual(result.status_code, 403)
        result = self.client.post("/api/off", json={}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(result.status_code, 403)

    def test_accepts_same_origin_control(self):
        self.assertEqual(self.client.post("/api/off", json={}, headers={"Origin": "http://localhost"}).status_code, 200)

    def test_rejects_untrusted_host(self):
        self.assertEqual(self.client.get("/api/status", headers={"Host": "example.com"}).status_code, 400)

    def test_rejects_invalid_json_and_content_type(self):
        self.assertEqual(self.client.post("/api/off", data="{}", content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.post("/api/off", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/off", json=[]).status_code, 400)

    def test_input_size_limits(self):
        self.assertEqual(self.client.get("/api/buildings?q=" + "a" * 81).status_code, 400)
        self.assertEqual(self.client.post("/api/off", json={"padding": "x" * 5000}).status_code, 413)

    def test_status_and_ports(self):
        self.assertEqual(self.client.get("/api/status").json["status"]["mode"], "simulation")
        self.assertEqual(self.client.get("/api/ports").json, {"ports": []})

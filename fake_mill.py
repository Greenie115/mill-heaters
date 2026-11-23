"""Dev only: fake Mill cloud + serves index.html, to test the page without real heaters.
python fake_mill.py  -> open http://127.0.0.1:8765, then in devtools:
localStorage.millApi='http://127.0.0.1:8765/'; location.reload()   (login: any email, password "pw")
"""
import json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

now = lambda: int(time.time() * 1000)
house = {"id": "h1", "name": "Home", "isVacationModeActive": False, "vacationEndDate": None}
rooms = {"r1": {"id": "r1", "name": "Bedroom", "averageTemperature": 18.6, "mode": "weekly_program",
                "activeModeFromWeeklyProgram": "sleep", "roomProgramName": "Weekdays", "overrideModeType": None,
                "roomComfortTemperature": 21, "roomSleepTemperature": 18, "roomAwayTemperature": 15},
         "r2": {"id": "r2", "name": "Living room", "averageTemperature": 20.9, "mode": "weekly_program",
                "activeModeFromWeeklyProgram": "comfort", "roomProgramName": "Weekdays", "overrideModeType": None,
                "roomComfortTemperature": 21.5, "roomSleepTemperature": 17, "roomAwayTemperature": 14}}
devs = {"d1": {"room": "r1", "name": "Bedroom panel", "online": False, "on": True, "seen": now() - 3 * 864e5},
        "d2": {"room": "r2", "name": "Sofa heater", "online": True, "on": True, "seen": now() - 6e4},
        "d3": {"room": None, "name": "Garage", "online": True, "on": True, "seen": now() - 6e4, "t": 12}}
tokens = {"id": 0}
log = []


def dev(i):
    d = devs[i]
    return {"deviceId": i, "customName": d["name"], "isConnected": d["online"], "isEnabled": d["on"], "roomId": d["room"],
            "deviceType": {"parentType": {"name": "Heaters"}, "childType": {"name": "GL-Panel G3"}},
            "lastMetrics": {"temperatureAmbient": 11.5 if i == "d3" else 20.9, "temperature": d.get("t", 20), "heaterFlag": 1,
                            "currentPower": 600 if d["online"] else 0, "time": d["seen"]},
            "deviceSettings": {"desired": {"operation_mode": "weekly_program"}}}


class H(BaseHTTPRequestHandler):
    def _j(self, code, obj):
        self.send_response(code); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        for h in ("Origin", "Methods", "Headers"): self.send_header(f"Access-Control-Allow-{h}", "*")
        self.end_headers()

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def _authed(self):
        if self.headers.get("Authorization") != f"Bearer id{tokens['id']}":
            self._j(401, {}); return False
        return True

    def _rec(self, b=None):
        log.append((self.command, self.path, b)); print(self.command, self.path, b, flush=True)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            return self.wfile.write(Path(__file__).with_name("index.html").read_bytes())
        if not self._authed(): return
        p = self.path
        if p == "/houses": return self._j(200, {"ownHouses": [house], "sharedHouses": []})
        if p == "/houses/h1/devices":
            return self._j(200, [{"roomId": r, "roomName": rooms[r]["name"], "devices": [dev(i) for i in devs if devs[i]["room"] == r]} for r in rooms])
        if p == "/houses/h1/devices/independent": return self._j(200, {"items": [dev(i) for i in devs if not devs[i]["room"]]})
        if p.startswith("/rooms/"): return self._j(200, rooms[p.split("/")[2]])
        self._j(404, {"error": "not found"})

    def do_POST(self):
        p = self.path
        if p.startswith("/customer/auth/"):
            b = self._body()
            if p.endswith("sign-in") and b.get("password") != "pw": return self._j(400, {"error": "Incorrect login or password"})
            if p.endswith("refresh") and self.headers.get("Authorization") != "Bearer refresh": return self._j(401, {})
            tokens["id"] += 1
            return self._j(200, {"idToken": f"id{tokens['id']}", "refreshToken": "refresh"})
        if not self._authed(): return
        b = self._body(); self._rec(b)
        if p.endswith("/mode/override"):
            r = rooms[p.split("/")[2]]; r.update(mode=b["mode"], overrideModeType=b["overrideModeType"])
        elif p.endswith("/temperature"):
            rooms[p.split("/")[2]].update(b)
        elif p == "/houses/h1/mode/vacation":
            house.update(isVacationModeActive=True, vacationEndDate=b["endDate"])
            for r in rooms.values(): r["mode"] = "vacation"
        self._j(200, {})

    def do_DELETE(self):
        if not self._authed(): return
        p = self.path; self._rec()
        if p.endswith("/mode/override"):
            rooms[p.split("/")[2]].update(mode="weekly_program", overrideModeType=None)
        elif p == "/houses/h1/mode/vacation":
            house.update(isVacationModeActive=False, vacationEndDate=None)
            for r in rooms.values(): r["mode"] = "weekly_program"
        self._j(200, {})

    def do_PATCH(self):
        if not self._authed(): return
        b, i = self._body(), self.path.split("/")[2]; self._rec(b)
        mode = b["settings"].get("operation_mode")
        if mode == "control_individually" and devs[i]["room"] is None:  # what the old page did -> real cloud 409'd
            return self._j(409, {"errorCode": 409, "error": "Conflict"})
        devs[i]["on"] = b["enabled"]
        if "temperature_normal" in b["settings"]: devs[i]["t"] = b["settings"]["temperature_normal"]
        self._j(200, {})

    def log_message(self, *a): pass


if __name__ == "__main__":
    print("http://127.0.0.1:8765", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()

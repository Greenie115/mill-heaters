"""Dev only: fake Mill cloud + serves index.html, to test the page without real heaters.
python fake_mill.py  -> open http://127.0.0.1:8765, then in devtools:
localStorage.millApi='http://127.0.0.1:8765/'; location.reload()   (login: any email, password "pw")
"""
import json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

now = lambda: int(time.time() * 1000)
state = {"d1": {"on": True, "t": 21.0}, "d2": {"on": True, "t": 20.0}}
tokens = {"id": 0}


def heater(i, name, online, seen):
    return {"deviceId": i, "customName": name, "isConnected": online,
            "deviceType": {"parentType": {"name": "Heaters"}, "childType": {"name": "GL-Panel G3"}},
            "lastMetrics": {"temperatureAmbient": 18.6 if i == "d1" else 20.9, "temperature": state[i]["t"],
                            "heaterFlag": 1, "currentPower": 600 if i == "d2" else 0, "time": seen},
            "deviceSettings": {"desired": {"operation_mode": "control_individually" if state[i]["on"] else "off"}}}


class H(BaseHTTPRequestHandler):
    def _j(self, code, obj):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        for h in ("Origin", "Methods", "Headers"):
            self.send_header(f"Access-Control-Allow-{h}", "*")
        self.end_headers()

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

    def _authed(self):
        if self.headers.get("Authorization") != f"Bearer id{tokens['id']}":
            self._j(401, {}); return False
        return True

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            return self.wfile.write(Path(__file__).with_name("index.html").read_bytes())
        if not self._authed(): return
        self._j(200, {"/houses": {"ownHouses": [{"id": "h1"}]},
                      "/houses/h1/devices": [{"roomId": "r1", "roomName": "Bedroom",
                                              "devices": [heater("d1", "Bedroom panel", False, now() - 3 * 86400000)]}],
                      "/houses/h1/devices/independent": {"items": [heater("d2", "Living room", True, now() - 60000)]}}[self.path])

    def do_POST(self):
        b = self._body()
        if self.path == "/customer/auth/sign-in":
            if b.get("password") != "pw":
                return self._j(400, {"error": "Incorrect login or password"})
        elif self.path == "/customer/auth/refresh":
            if self.headers.get("Authorization") != "Bearer refresh": return self._j(401, {})
        tokens["id"] += 1
        self._j(200, {"idToken": f"id{tokens['id']}", "refreshToken": "refresh"})

    def do_PATCH(self):
        if not self._authed(): return
        b, dev = self._body(), self.path.split("/")[2]
        print("PATCH", self.path, b, flush=True)
        s = b["settings"]
        state[dev]["on"] = s["operation_mode"] != "off"
        if "temperature_normal" in s: state[dev]["t"] = s["temperature_normal"]
        self._j(200, {})

    def log_message(self, *a): pass


if __name__ == "__main__":
    print("http://127.0.0.1:8765", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()

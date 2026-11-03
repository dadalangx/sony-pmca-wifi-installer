"""Fixed-purpose camera installer page. No remote shell or arbitrary file API."""
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs, urlsplit


class InstallerServer:
    def __init__(self, adapter, package, on_event=lambda *args: None, port=80):
        self.adapter, self.package, self.on_event = adapter, package, on_event
        self.token = secrets.token_hex(16)
        self.prefix = "/s/" + self.token
        self.phase, self.camera = "waiting", None
        self.lock = threading.RLock()
        self.http, self.worker = None, None
        self.port = port

    def config(self):
        return {**self.package.camera_config(), "prefix": self.prefix, "phase": self.phase,
                "target": "/data/local/tmp/com.sony.scalar.dlsys.scalaramarket/SonyWifi-" + self.token + ".1.spk"}

    def report(self, kind, data):
        with self.lock:
            allowed = {
                "ready": {"waiting", "ready", "error"},
                "downloading": {"waiting", "ready", "error", "installing"},
                "prepared": {"downloading"},
                "opening": {"prepared"},
                "verified": {"prepared", "installing", "waiting", "ready"},
                "error": {"waiting", "ready", "downloading", "prepared", "installing", "error"},
            }
            if kind not in allowed or self.phase not in allowed[kind]:
                return False
            if kind == "verified" and (data.get("md5") != self.package.apk_md5 or data.get("cleaned") is not True):
                return False
            self.phase = {"opening": "installing", "verified": "done"}.get(kind, kind)
            self.on_event(kind, data)
            return True

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def response(self, body=b"", status=200, mime="text/plain; charset=utf-8", location=None):
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                if location is not None:
                    self.send_header("Location", location)
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                self.close_connection = True

            def do_GET(self):
                remote = self.client_address[0]
                if ipaddress.ip_address(remote) not in owner.adapter.network:
                    self.response(status=403)
                    return
                path = urlsplit(self.path).path
                if path in ("/", "/portal/noauth/blank.htm", "/portal/noauth/service_close.html"):
                    # Preserve the Sony origin: an absolute LAN-IP redirect
                    # causes the factory application to report server failure.
                    self.response(status=302, location=owner.prefix + "/")
                    return
                if not path.startswith(owner.prefix + "/"):
                    self.response(status=404)
                    return
                with owner.lock:
                    if owner.camera is not None and remote != owner.camera:
                        self.response(status=403)
                        return
                    # Camera identification avoids a phone claiming the session.
                    if "sccamera" not in self.headers.get("User-Agent", "").lower():
                        self.response(b"Open this page in the camera's PlayMemories application.", status=403)
                        return
                    owner.camera = remote
                suffix = path[len(owner.prefix):]
                if suffix == "/":
                    cfg = json.dumps(owner.config(), ensure_ascii=True).replace("<", "\\u003c")
                    page = ("<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
                            "<title>Sony Wi-Fi Installer</title><style>body{font:21px sans-serif;background:white;color:#111;margin:12px}"
                            "button{font:22px sans-serif;padding:14px;width:100%;margin:8px 0}</style></head><body>"
                            "<h2>Sony Wi-Fi Installer</h2><p>" + html.escape(owner.package.name) + "</p>"
                            "<p id='status'>Checking camera...</p><button id='install' style='display:none'>Install app</button>"
                            "<script>window.CFG=" + cfg + ";</script><script src='" + owner.prefix + "/camera.js'></script></body></html>").encode()
                    self.response(page, mime="text/html; charset=utf-8")
                elif suffix == "/camera.js":
                    self.response(Path(__file__).with_name("camera.js").read_bytes(), mime="application/javascript")
                elif suffix == "/app.spk":
                    if owner.phase != "downloading":
                        self.response(status=409)
                    else:
                        self.response(owner.package.spk, mime="application/octet-stream")
                elif suffix == "/report":
                    if self.command == "HEAD":
                        self.response(status=405)
                        return
                    query = urlsplit(self.path).query
                    if len(query) > 8192:
                        self.response(status=413)
                        return
                    try:
                        params = parse_qs(query, max_num_fields=4)
                        kind = params["event"][0]
                        data = json.loads(params["data"][0])
                        if not isinstance(data, dict):
                            raise ValueError("Invalid report")
                        accepted = owner.report(kind, data)
                    except (KeyError, ValueError, TypeError):
                        self.response(status=400)
                        return
                    self.response(b"OK", status=200 if accepted else 409)
                else:
                    self.response(status=404)

            do_HEAD = do_GET

        self.http = ThreadingHTTPServer((self.adapter.ip, self.port), Handler)
        self.http.daemon_threads = True
        self.worker = threading.Thread(target=self.http.serve_forever, name="camera-http", daemon=True)
        self.worker.start()

    def close(self):
        if self.http:
            if self.worker:
                self.http.shutdown()
            self.http.server_close()
            self.http = None

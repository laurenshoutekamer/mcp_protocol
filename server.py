#imports
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from datetime import date
import subprocess
import time
import base64
import math 


class Handler(BaseHTTPRequestHandler):

    def reply(self, status, message):
        body = json.dumps(message).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/mcp":
            self.reply(404, {"error": "wrong path"})
            return

        size = self.headers.get("Content-Length")
        if size is None:
            self.reply(400, {"error": "missing Content-Length"})
            return
        size = int(size)
        if size < 0 or size > 1_000_000:
            self.reply(400, {"error": "bad body size"})
            return

        raw = self.rfile.read(size)
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.reply(400, {"error": "invalid JSON"})
            return

        if not isinstance(request, dict):
            self.reply(400, {"error": "invalid request"})
            return

        self.reply(200, {"you_sent": request})


if __name__ == "__main__":
    mcp_server = ThreadingHTTPServer(("127.0.0.1", 8123), Handler)
    print("listening on http://127.0.0.1:8123/mcp")
    mcp_server.serve_forever()


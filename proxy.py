#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

PORT = 8080

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Expected path: /paste/<id>
        if not self.path.startswith("/paste/"):
            self.send_error(404, "Invalid path")
            return

        paste_id = self.path.split("/paste/")[1].strip()
        if not paste_id:
            self.send_error(400, "Missing paste ID")
            return

        url = f"https://pastebin.com/raw/{paste_id}"

        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.send_error(502, str(e))
            return

        data = r.text.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

#    def log_message(self, *args):
        # Silence logging
#        pass

if __name__ == "__main__":
    print(f"Pastebin proxy listening on port {PORT}")
    HTTPServer(("", PORT), ProxyHandler).serve_forever()

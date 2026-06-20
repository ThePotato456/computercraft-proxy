#!/usr/bin/env python3
"""
ComputerCraft Unified Proxy w/ Logging
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import json
import os
import requests
from openai import OpenAI

PORT = 8080

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# -------------------------------------------------
# Logging helper
# -------------------------------------------------

def log(msg):
    """Print timestamped log message."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


# -------------------------------------------------
# HTTP Handler
# -------------------------------------------------

class ProxyHandler(BaseHTTPRequestHandler):

    # ---------- helpers ----------

    def client_ip(self):
        return self.client_address[0]

    def send_text(self, code, data):
        encoded = data.encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

        log(f"{self.client_ip()} -> TEXT {code} ({len(encoded)} bytes)")

    def send_json(self, code, obj):
        encoded = json.dumps(obj).encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

        log(f"{self.client_ip()} -> JSON {code} ({len(encoded)} bytes)")

    # ---------- GET ----------

    def do_GET(self):

        log(f"{self.client_ip()} GET {self.path}")

        if self.path.startswith("/paste/"):

            paste_id = self.path.split("/paste/")[1].strip()

            if not paste_id:
                log("ERROR: Missing paste ID")
                self.send_error(400, "Missing paste ID")
                return

            url = f"https://pastebin.com/raw/{paste_id}"

            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()

                log(f"Fetched pastebin {paste_id}")

            except Exception as e:
                log(f"ERROR fetching paste: {e}")
                self.send_error(502, str(e))
                return

            self.send_text(200, r.text)
            return

        log("Invalid GET endpoint")
        self.send_error(404, "Invalid endpoint")

    # ---------- POST ----------

    def do_POST(self):

        log(f"{self.client_ip()} POST {self.path}")

        if self.path != "/chat":
            log("Invalid POST endpoint")
            self.send_error(404, "Invalid endpoint")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)

            prompt = data.get("prompt", "")

            log(f"Prompt received ({len(prompt)} chars)")

        except Exception as e:
            log(f"ERROR parsing JSON: {e}")
            self.send_error(400, "Invalid JSON")
            return

        if not prompt:
            log("ERROR: Empty prompt")
            self.send_error(400, "Missing prompt")
            return

        # ----- OpenAI request -----

        try:
            log("Sending request to OpenAI...")

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )

            reply = response.choices[0].message.content

            log(f"OpenAI response received ({len(reply)} chars)")

        except Exception as e:
            log(f"OPENAI ERROR: {e}")
            self.send_json(500, {"error": str(e)})
            return

        self.send_json(200, {"reply": reply})

    # Disable default logging completely
    def log_message(self, *args):
        pass


# -------------------------------------------------
# Server start
# -------------------------------------------------

if __name__ == "__main__":
    log(f"ComputerCraft proxy listening on port {PORT}")
    HTTPServer(("", PORT), ProxyHandler).serve_forever()

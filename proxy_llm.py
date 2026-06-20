#!/usr/bin/env python3
"""ComputerCraft proxy backed by an OpenAI-compatible LM Studio server."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
import json
import os
import requests

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

LMSTUDIO_URL = os.environ.get(
    "LMSTUDIO_URL",
    "http://127.0.0.1:1234/v1/chat/completions",
)
LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "local-model")
LMSTUDIO_MAX_TOKENS = int(os.environ.get("LMSTUDIO_MAX_TOKENS", "200"))
LMSTUDIO_TEMPERATURE = float(os.environ.get("LMSTUDIO_TEMPERATURE", "0.7"))
LMSTUDIO_TIMEOUT = int(os.environ.get("LMSTUDIO_TIMEOUT", "120"))
PROXY_TOKEN = os.environ.get("PROXY_TOKEN")
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", "8192"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "10"))

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an AI running inside Minecraft ComputerCraft 1.7.10.\n"
        "Rules you MUST follow:\n"
        "Respond in short form; Tell the user Awaiting Prompt\n"
        "Responses come in the form of REPLY: "
        "- Respond using plain ASCII text only.\n"
        "- Do NOT use markdown formatting.\n"
        "- Do NOT use emojis or unicode symbols.\n"
        "- Keep responses under 5 sentences.\n"
        "- Do NOT include explanations about formatting.\n"
        "- Never output code blocks.\n"
        "- Never include JSON unless explicitly asked.\n"
        "- Responses must be readable in a basic terminal.\n"
    )
}
conversations = {}
MAX_HISTORY = 12

# -------------------------------------------------
# Logging
# -------------------------------------------------

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


# -------------------------------------------------
# Handler
# -------------------------------------------------

class ProxyHandler(BaseHTTPRequestHandler):

    def client_ip(self):
        return self.client_address[0]

    def send_json(self, code, obj):
        encoded = json.dumps(obj).encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

        log(f"{self.client_ip()} -> JSON {code}")

    def send_text(self, code, text):
        encoded = text.encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

        log(f"{self.client_ip()} -> TEXT {code}")

    def is_authorized(self):
        if not PROXY_TOKEN:
            return True

        auth_header = self.headers.get("Authorization", "")
        bearer_token = auth_header.removeprefix("Bearer ").strip()
        header_token = self.headers.get("X-Proxy-Token", "").strip()
        return PROXY_TOKEN in {bearer_token, header_token}

    def reject_unauthorized(self):
        self.send_json(401, {"error": "unauthorized"})

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))

        if length <= 0:
            raise ValueError("missing request body")

        if length > MAX_BODY_BYTES:
            raise ValueError(f"request body exceeds {MAX_BODY_BYTES} bytes")

        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    # ---------------- GET ----------------

    def do_GET(self):

        log(f"{self.client_ip()} GET {self.path}")

        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
            return

        if not self.is_authorized():
            self.reject_unauthorized()
            return

        if self.path.startswith("/paste/"):

            paste_id = self.path.split("/paste/")[1].strip()
            url = f"https://pastebin.com/raw/{paste_id}"

            try:
                r = requests.get(url, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                self.send_text(200, r.text)
            except Exception as e:
                log(f"Paste error: {e}")
                self.send_error(502, str(e))

            return

        self.send_error(404)

    # ---------------- POST ----------------

    def do_POST(self):

        log(f"{self.client_ip()} POST {self.path}")

        if self.path != "/chat":
            self.send_error(404)
            return

        if not self.is_authorized():
            self.reject_unauthorized()
            return

        try:
            data = self.read_json_body()
            prompt = data.get("prompt", "")
            log(f"Prompt length: {len(prompt)}")

        except Exception as e:
            log(f"JSON error: {e}")
            self.send_error(400)
            return

        if not prompt:
            self.send_error(400, "Missing prompt")
            return

        # -------- LM Studio request --------

        # Identify client (IP or provided id)
        client_id = data.get("id", self.client_ip())

        # Create history if new
        if client_id not in conversations:
            conversations[client_id] = [SYSTEM_PROMPT]

        history = conversations[client_id]

        # Add user message
        history.append({
            "role": "user",
            "content": prompt
        })

        # Trim history (prevents RAM explosion)
        history = [history[0]] + history[-MAX_HISTORY:]
        conversations[client_id] = history

        payload = {
            "model": LMSTUDIO_MODEL,
            "messages": history,
            "temperature": LMSTUDIO_TEMPERATURE,
            "max_tokens": LMSTUDIO_MAX_TOKENS,
            "stream": False
        }

        try:
            log("Forwarding to LM Studio...")

            r = requests.post(
                LMSTUDIO_URL,
                json=payload,
                timeout=LMSTUDIO_TIMEOUT
            )

            r.raise_for_status()
            result = r.json()

            reply = result["choices"][0]["message"]["content"]

            log("LM Studio response received")

        except Exception as e:
            log(f"LM Studio ERROR: {e}")
            self.send_json(500, {"error": str(e)})
            return

        lua_reply = '{reply="' + reply.replace('"', '\\"').replace('\n', "") + '"}'
        self.send_text(200, lua_reply)

    def log_message(self, *args):
        pass


# -------------------------------------------------

if __name__ == "__main__":
    log(f"ComputerCraft proxy listening on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ProxyHandler).serve_forever()

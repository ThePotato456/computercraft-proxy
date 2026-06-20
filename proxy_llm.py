#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import json
import requests

# Port the api is hosted on
PORT = 8080

# LM Studio OpenAI-compatible endpoint
LMSTUDIO_URL = "http://192.168.1.245:1234/v1/chat/completions"

# conversation storage
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

    # ---------------- GET ----------------

    def do_GET(self):

        log(f"{self.client_ip()} GET {self.path}")

        if self.path.startswith("/paste/"):

            paste_id = self.path.split("/paste/")[1].strip()
            url = f"https://pastebin.com/raw/{paste_id}"

            try:
                r = requests.get(url, timeout=10)
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

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)

            prompt = data.get("prompt", "")
            log(f"Prompt length: {len(prompt)}")

        except Exception as e:
            log(f"JSON error: {e}")
            self.send_error(400)
            return

        # -------- LM Studio request --------

        payload_old = {
            "model": "local-model",  # ignored by LM Studio but required
            "messages": [
                {"role": "system", "content": "respond with only plaintext"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": False
        }

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

        payload = {
            "model": "local-model",
            "messages": history,
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": False
        }    

        try:
            log("Forwarding to LM Studio...")

            r = requests.post(
                LMSTUDIO_URL,
                json=payload,
                timeout=120
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
        #self.send_json(200, {"reply": reply})

    def log_message(self, *args):
        pass


# -------------------------------------------------

if __name__ == "__main__":
    log(f"ComputerCraft proxy listening on port {PORT}")
    HTTPServer(("", PORT), ProxyHandler).serve_forever()

# ComputerCraft Proxy

Small HTTP proxy for Minecraft ComputerCraft clients that need simple access to Pastebin and chat completion APIs.

The project includes two server variants:

- `proxy.py`: Pastebin proxy plus `/chat` backed by the OpenAI API.
- `proxy_llm.py`: Pastebin proxy plus `/chat` backed by an OpenAI-compatible LM Studio server.

## Features

- `GET /paste/<paste_id>` fetches raw Pastebin content.
- `POST /chat` accepts a JSON prompt and returns a short model response.
- `GET /healthz` returns a health check response.
- Runtime configuration is handled through environment variables.
- Optional shared-token authentication for LAN deployments.
- Request size limits, upstream timeouts, and threaded request handling.

## Requirements

- Python 3.10 or newer
- Network access from the proxy host to Pastebin
- One of:
  - OpenAI API key for `proxy.py`
  - LM Studio or another OpenAI-compatible local server for `proxy_llm.py`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for your environment before starting a server.

## Configuration

Common settings:

| Variable | Default | Description |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `PROXY_TOKEN` | unset | Optional shared token. When set, clients must send it. |
| `MAX_BODY_BYTES` | `8192` | Maximum JSON request body size. |
| `REQUEST_TIMEOUT` | `10` | Pastebin request timeout in seconds. |

OpenAI settings for `proxy.py`:

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | required | OpenAI API key. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Chat completion model. |
| `OPENAI_MAX_TOKENS` | `200` | Maximum model response tokens. |

LM Studio settings for `proxy_llm.py`:

| Variable | Default | Description |
| --- | --- | --- |
| `LMSTUDIO_URL` | `http://127.0.0.1:1234/v1/chat/completions` | OpenAI-compatible chat completions endpoint. |
| `LMSTUDIO_MODEL` | `local-model` | Model name sent to the endpoint. |
| `LMSTUDIO_MAX_TOKENS` | `200` | Maximum model response tokens. |
| `LMSTUDIO_TEMPERATURE` | `0.7` | Sampling temperature. |
| `LMSTUDIO_TIMEOUT` | `120` | Chat request timeout in seconds. |

## Run

OpenAI-backed server:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python proxy.py
```

LM Studio-backed server:

```bash
source .venv/bin/activate
set -a
source .env
set +a
python proxy_llm.py
```

## API

Health check:

```bash
curl http://localhost:8080/healthz
```

Fetch a Pastebin paste:

```bash
curl http://localhost:8080/paste/PASTE_ID
```

Send a chat prompt:

```bash
curl -X POST http://localhost:8080/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Hello"}'
```

If `PROXY_TOKEN` is set, include either header:

```bash
curl -H "Authorization: Bearer $PROXY_TOKEN" http://localhost:8080/healthz
curl -H "X-Proxy-Token: $PROXY_TOKEN" http://localhost:8080/paste/PASTE_ID
```

## ComputerCraft Notes

For Pastebin proxying, request:

```lua
local res = http.get("http://SERVER_IP:8080/paste/PASTE_ID")
```

For chat, post JSON to `/chat` with a `prompt` field. `proxy_llm.py` returns a Lua-style text table for older ComputerCraft flows:

```text
{reply="..."}
```

`proxy.py` returns JSON:

```json
{"reply":"..."}
```

## Deployment Notes

Run this behind a firewall or on a trusted LAN. Set `PROXY_TOKEN` before exposing it to other machines. For internet-facing deployment, put it behind a reverse proxy that provides TLS, rate limiting, and access logging.

Do not commit `.env` or API keys. The included `.gitignore` excludes local environment files.

# callguard
A real-time voice AI agent that listens to your calls, spots scams as they happen, and quietly warns you in your ear before you hand over money or codes.

This is a prototype for the Hiya Voice AI Challenge.

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python dependencies)
- Python 3.12 or newer
- Node.js 20.9 or newer
- `make`

## Run locally

Use two terminals, from the repo root. Each command installs its own dependencies.

```bash
make backend    # http://localhost:8100
make frontend   # http://localhost:3100
```

Open http://localhost:3100. Backend health should read `ok`, the WebSocket should read `connected`, and the log should show a pong with its round-trip time. If you stop the backend the page shows `disconnected`, and it reconnects by itself when the backend returns.

## Configuration

Backend settings are all in `backend/app/config.py`, and each can be overridden by an environment variable. Frontend settings are in `frontend/lib/config.ts`.

To override values from a file, copy `backend/.env.example` to `backend/.env`, or `frontend/.env.example` to `frontend/.env.local`. Both copies are ignored by git.

The frontend port is set in the scripts in `frontend/package.json`. If you change either port, also update `CORS_ORIGINS` or `NEXT_PUBLIC_BACKEND_URL` to match.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Returns `{"status": "ok"}` |
| `WS /ws` | Sends `{"type": "connected"}` on connect, and answers `{"type": "ping", "sent_at": ...}` with a `pong` |

## Project structure

```
backend/app/config.py    all backend settings
backend/app/api.py       health check and WebSocket routes
backend/app/main.py      creates and starts the FastAPI app
frontend/lib/config.ts   all frontend settings
frontend/app/page.tsx    the single page, connects to the backend
frontend/app/layout.tsx  HTML shell for the page
```

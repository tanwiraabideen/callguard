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

To try a simulated call, pick one and press **Play call**. You'll hear it, and the page shows how many seconds the browser has played and the backend has received.

## Call audio

The scripts are in `backend/calls/scripts/`. Their generated audio and word timings are in `backend/calls/generated/` and are committed, so running the project needs no ElevenLabs key.

In a script, `first_red_flag` marks where the first real red flag occurs, `trigger` marks the user's spoken help phrases, and a negative `gap_ms` makes a turn interrupt the one before it.

If you edit or add a script, put `ELEVENLABS_API_KEY` in `backend/.env` and run this. It spends credits, and it skips any call that already has audio, so delete the old `.wav` first or run the tool with `--force`.

```bash
make audio
```

## Configuration

Backend settings are all in `backend/app/config.py`, and each can be overridden by an environment variable. Frontend settings are in `frontend/lib/config.ts`.

To override values from a file, copy `backend/.env.example` to `backend/.env`, or `frontend/.env.example` to `frontend/.env.local`. Both copies are ignored by git.

The frontend port is set in the scripts in `frontend/package.json`. If you change either port, also update `CORS_ORIGINS` or `NEXT_PUBLIC_BACKEND_URL` to match.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Returns `{"status": "ok"}` |
| `GET /calls` | Lists the simulated calls |
| `GET /calls/{id}/audio` | Returns a call's stereo WAV file |
| `WS /ws` | JSON messages: `ping`, `call_start` and `call_end`. Binary frames: call audio as 16-bit stereo at 16 kHz, left = caller, right = user |

## Project structure

```
backend/app/config.py    all backend settings
backend/app/api.py       HTTP and WebSocket routes
backend/app/call_session.py  handles one browser's messages and call audio
backend/app/calls.py     finds call scripts and audio on disk
backend/app/main.py      creates and starts the FastAPI app
backend/calls/           call scripts and generated audio
backend/tools/generate_audio.py  turns scripts into audio with ElevenLabs
frontend/lib/config.ts   all frontend settings
frontend/lib/callPlayer.ts  plays a call and streams it to the backend
frontend/app/page.tsx    the single page, connects to the backend
frontend/app/layout.tsx  HTML shell for the page
```

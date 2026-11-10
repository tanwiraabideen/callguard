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

To try a simulated call, pick one and press **Play call**. You'll hear it, and the page shows the live transcript, risk score, alerts and a "behind the scenes" log of every decision. A summary card appears when the call ends.

To play the scammer yourself, press **Try to scam me (microphone)** in Chrome and improvise. Calls are capped at 3 minutes. Your voice is the caller. To answer as the person being scammed, hold the button that appears while you speak. Live calls need `ELEVENLABS_API_KEY`.

**No keys are needed for simulated calls.** Each key adds something:

| Key in `backend/.env` | With it | Without it |
| --- | --- | --- |
| `ELEVENLABS_API_KEY` | Real transcription and natural voices, and live calls work | Mock transcript and the browser's own voice, and no live calls |
| `ANTHROPIC_API_KEY` | Claude for the risk check and the agent | Rules and voice pressure, and the agent follows a fixed plan |
| `LANGSMITH_API_KEY` | Agent runs are traced, with a link on the page | No tracing |

## Transcription

The page shows a live transcript labelled by speaker, and says which mode produced it.

- **Mock mode** needs no keys. It replays each script's words with their real timings, released as the call audio arrives.
- **Real mode** streams each channel to ElevenLabs Scribe. Add `ELEVENLABS_API_KEY` to `backend/.env` to use it. A restricted key needs its speech-to-text permission on.

By default the backend uses ElevenLabs if a key is set, and mock mode if not. Set `TRANSCRIPTION_MODE=mock` or `TRANSCRIPTION_MODE=elevenlabs` to force one. If ElevenLabs fails during a call, the page logs an error and does not switch to mock mode, so a mock transcript can't be mistaken for a real one.

## Risk engine

Each final sentence goes through `backend/app/risk/`, and the page shows a running score from 0 to 100.

- **Tier 1, rules:** weighted red-flag checks on every caller sentence.
- **Voice pressure:** caller speaking rate, interruptions and share of talk time, from word timestamps. Pressure alone is capped at a small number of points.
- **Tier 2, LLM:** a small Claude model judges the last few sentences, but only when Tier 1 or pressure fires. Add `ANTHROPIC_API_KEY` to `backend/.env` to use it. Without a key the engine runs on rules alone.

Red flags add points, the LLM's score is blended in to give a target, and the score moves part of the way to the target on each sentence, so it builds over a call. All weights and thresholds are in `backend/app/config.py`.

## Alerts and dismissal

Medium risk shows an alert with the reason. High risk also lowers the caller's audio and plays a short whisper, which stays in the browser and never enters the call.

**Not a scam** lowers the points for that kind of red flag and ignores repeats of it. Every dismissal is logged. Pressure tactics such as urgency count as less severe, so dismissing them can't silence a later request for codes, money or remote access, which alerts again.

## The agent

The user asks for help by saying a trigger phrase to the caller. The phrases are in `TRIGGER_PHRASES`, by default "let me grab a pen" and "let me find my glasses".

- **First trigger:** the agent looks up an official number and whispers advice.
- **Second trigger, or 20 seconds of user silence at high risk:** the agent speaks to the caller, writes a summary and ends the call.

The agent is a LangGraph loop in `backend/app/agent/graph.py` with a limit on steps. Claude chooses the tools. If there's no key, or a request fails, a fixed plan in `policy.py` does the job through the same tools. Code, not the model, stops the agent speaking to the caller or ending a call during the advice step.

Official numbers are in `backend/app/agent/official_numbers.json`, each with its source. The agent can't give any other number.

## Evaluation

```bash
make eval
```

This runs every call through detection in mock mode, prints a table, and saves it to `backend/eval/results.md` and `results.json`. It uses the Claude risk check if a key is set. To measure without it, run `uv run python -m tools.evaluate --rules-only` in `backend`, which saves to `results_rules_only.md`. A negative delay means the alert came before the labelled first red flag.

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
| `WS /ws` | JSON messages: `ping`, `call_start`, `call_end` and `dismiss_alert`. Binary frames: call audio as 16-bit stereo at 16 kHz, left = caller, right = user |

## Project structure

```
backend/app/config.py    all backend settings
backend/app/api.py       HTTP and WebSocket routes
backend/app/call_session.py  handles one browser's messages and call audio
backend/app/calls.py     finds call scripts and audio on disk
backend/app/transcription/  real (ElevenLabs) and mock transcribers
backend/app/risk/        rules, voice pressure, LLM check, score, and alerts
backend/app/agent/       trigger phrases, tools, fixed plan, and the LangGraph agent
backend/app/speech.py    turns whispers and the agent's voice into audio
backend/app/summary.py   builds the post-call card
backend/app/claude.py    the shared Claude client
backend/app/tracing.py   LangSmith set-up
backend/app/trace.py     the format of a "behind the scenes" entry
backend/app/main.py      creates and starts the FastAPI app
backend/calls/           call scripts and generated audio
backend/eval/            saved evaluation results
backend/tools/generate_audio.py  turns scripts into audio with ElevenLabs
backend/tools/evaluate.py        runs the evaluation
frontend/lib/config.ts   all frontend settings
frontend/lib/callPlayer.ts  plays a call and streams it to the backend
frontend/lib/micCall.ts     streams the microphone to the backend
frontend/lib/speechPlayer.ts  plays whispers and the agent's voice
frontend/public/micProcessor.js  collects microphone audio
frontend/app/page.tsx    the single page's layout
frontend/app/useCall.ts  the page's state and backend messages
frontend/app/Transcript.tsx, RiskPanel.tsx, RiskChart.tsx  live call views
frontend/app/AlertList.tsx, TracePanel.tsx, SummaryCard.tsx  alerts, log, and card
frontend/app/layout.tsx  HTML shell for the page
```

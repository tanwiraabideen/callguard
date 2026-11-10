# Scam Call Copilot: Build Plan

## What we're building

A voice AI agent that listens to a phone call in real time, detects scam behaviour, and protects the user without them touching their screen.

- It listens to **what** the caller says (red flags like asking for a one-time code or a "safe account") and **how** they say it (speaking rate, talking over the user).
- It alerts the user privately: a visual alert at medium risk, and a quiet spoken whisper that only the user hears at high risk.
- The user can trigger help hands-free by saying a natural phrase to the caller ("hang on, let me grab a pen"). The agent then whispers advice, and if needed speaks for the user, ends the call and gives the official number to call back.
- The user can dismiss any alert ("Not a scam"). Dismissing lowers risk for that signal type, but a more serious signal still re-alerts.
- After the call, it shows a summary on screen.

This is a prototype for the Hiya Voice AI Challenge (Security / Real-Time Assistance track). Lo-fi UI is fine. It must run, and it must be obvious that the agent is really running, not replaying a fixed demo.

## How to work with me

- Build one stage at a time. At the end of each stage, stop, summarise what you built and why, and wait for me to review before moving on.
- Keep it simple and readable. I need to explain and debug every file in an interview, and add a feature live.
- Keep modules small and separated (transcription, risk engine, agent, alerts, API, UI).
- Put every model name, threshold, weight and feature switch in one config file, overridable by environment variables.
- Never commit secrets. Use a `.env.example`.
- When there is a real design choice, give me the options and trade-offs briefly and let me choose.

## Suggested stack (challenge me if something is a poor fit)

- Backend: Python, FastAPI, WebSockets
- Streaming speech-to-text: Deepgram (with word timestamps)
- LLM: OpenAI small model (e.g. GPT-5-nano) with structured output for risk scoring
- Agent: LangGraph, traced with LangSmith
- Text-to-speech for the whisper and the agent's voice: ElevenLabs or OpenAI TTS
- Frontend: Next.js / React, single page
- Hosting: frontend on Vercel, backend on a host that supports WebSockets (Render, Railway or Fly.io)

## Stages

### Stage 1: Project skeleton
- Set up the repo structure, config module, `.env.example`, and a basic README.
- Backend with a health check and a WebSocket endpoint; frontend page that connects to it.
- Done when: frontend and backend talk to each other locally with one command each (or one `docker compose up`).

### Stage 2: Call scripts and simulator
- Write 5 short call scripts (60 to 90 seconds each):
  1. Bank "safe account" scam
  2. HMRC tax threat scam
  3. Parcel redelivery fee scam
  4. Real bank calling about genuine fraud (hard negative: sounds alarming but never asks for codes or money moves)
  5. Normal call (e.g. dentist confirming an appointment)
- Each script includes a spoken trigger phrase moment where relevant, and labels for where the first real red flag occurs.
- Generate audio with two TTS voices, caller and user on separate channels.
- Add a simulator that streams a chosen call to the backend at real-time speed, while the browser plays it.
- Done when: I can pick a call in the UI and hear it play while audio streams to the backend.

### Stage 3: Live transcription
- Stream the caller channel and user channel to the speech-to-text service, keeping speaker and word timestamps.
- Show the live transcript in the UI, labelled by speaker.
- Add mock mode: replays the script's transcript with timings instead of calling the speech-to-text API, so it runs without keys. The detection and agent must still run live in mock mode.
- Done when: the transcript appears live for any call, in both real and mock mode.

### Stage 4: Risk engine
- Tier 1, rules: weighted red-flag checks run on every caller sentence (codes or PINs, safe account or moving money, gift cards or crypto, secrecy, urgency or threats, remote-access apps).
- Voice pressure signals from word timestamps: caller speaking rate, interruptions of the user, share of talk time.
- Tier 2, small LLM: runs on the last few sentences only when Tier 1 or pressure signals fire. Returns structured output: risk score, signals, one-line reason.
- Combine into a running call risk score that builds over the call rather than spiking on one sentence.
- Done when: the risk score updates live and scam calls climb while the legit calls stay low.

### Stage 5: Alerts and dismissal
- Medium risk: visual alert in the UI with the reason.
- High risk: briefly lower the caller audio and play a short whisper on the user's side only, never into the call.
- "Not a scam" button on each alert: lowers risk for that signal type and suppresses repeats, but a more severe signal re-alerts. Log every dismissal.
- Done when: alerts fire at the right moments, dismissal works, and a code request after a dismissal still re-alerts.

### Stage 6: The agent
- Detect the spoken trigger phrase in the user's speech (configurable list of phrases).
- On trigger, a LangGraph agent decides what to do, using tools:
  - `whisper_to_user`: short advice only the user hears
  - `say_to_caller`: speaks for the user (e.g. "I'll call my bank back on the number on my card")
  - `end_call`
  - `lookup_official_number`: from a small local list of real organisations' published numbers
  - `write_summary`
- If the user triggers twice or goes silent at high risk, the agent can take over the call.
- Add a step limit so it can't loop.
- Done when: saying the trigger phrase in a scam call leads to sensible advice, and a second trigger makes the agent speak to the caller and end the call.

### Stage 7: Make the agent's work visible
- Right-hand "behind the scenes" panel with a live trace log per sentence: rules fired, pressure signals, raw LLM output, model name, latency in ms, each tool call with inputs and outputs.
- Risk score chart over the call.
- Link to the LangSmith trace for the run.
- Post-call summary card: what happened, which red flags fired and when, any dismissed alerts, recommended next steps.
- Done when: someone watching can see every decision the system made and how long it took.

### Stage 8: "Try to scam me" live mode
- Live microphone mode where the reviewer plays the scammer and improvises.
- Same pipeline as the simulated calls.
- Cap call length (about 3 minutes).
- Done when: an unscripted scam I make up on the spot gets detected.

### Stage 9: Evaluation
- Script that runs every call through the engine in mock mode and prints a results table:
  - flagged or not
  - seconds from first labelled red flag to first alert
  - false alerts on the legit calls
- Add a few more scripts if useful (aim for 8 to 10 calls total), including at least one more hard negative.
- Save results to a file I can quote in the write-up.
- Done when: one command produces the table.

### Stage 10: Deploy and protect
- Deploy frontend and backend.
- Require a demo passcode, cap call length, and remind me to set spend limits on each API provider.
- Check cold-start behaviour on the host and note it in the README.
- Done when: the hosted link works end to end from a fresh browser.

### Stage 11: Docs and submission
- README.md: what it is, setup, run (real and mock mode), how to run the evaluation, hosted link and passcode instructions, project structure.
- ai.md: placeholder for me to write myself (which AI tools I used and how).
- Help me draft the 1-page write-up: what I built, who it's for, the problem, why voice is the right interface at each key moment, key design choices (tiered detection, whisper only at high risk, dismissal logic, false positives matter to legitimate businesses), evaluation results, and what I'd do next (on-device models for privacy, real call integration, more languages, synthetic voice detection).
- Test from a fresh clone before submitting.

## Out of scope

- Real telephony (e.g. Twilio)
- Modelling phone vibration
- User accounts or a database
- Deepfake / cloned voice detection (mention as a next step only)

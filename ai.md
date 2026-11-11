# AI use in this project

This covers two things: the AI models CallGuard uses while it runs, and the AI tools used to build it.

## AI inside CallGuard

| What | Model or service | Used for |
| --- | --- | --- |
| Call audio | ElevenLabs text-to-speech, `eleven_multilingual_v2` | Turning the call scripts into the caller and user voices. Done once, and the audio is committed. |
| Live transcription | ElevenLabs Scribe, `scribe_v2_realtime` | Turning each channel of the call into text with word timings. |
| Risk check (Tier 2) | Claude Haiku 5.5 | Judging the last few sentences, but only when a rule or a voice pressure signal has fired. |
| Agent | Claude Haiku 5.5, inside a LangGraph loop | Choosing tools when the user asks for help: whisper advice, look up an official number, speak to the caller, write a summary, end the call. |
| Spoken output | ElevenLabs text-to-speech, `eleven_flash_v2_5` | The whisper and the agent's voice. The browser's own voice is used if there's no key. |

Several important parts are deliberately **not** AI, so that they are predictable and can be explained:

- The Tier 1 red-flag rules, the voice pressure signals, and how the risk score is combined.
- When alerts fire, and how dismissals work.
- The safety limits on the agent: its step limit, the rule that it can't speak to the caller or end the call when only advising, the cap on whisper length, and the fixed list of official phone numbers.
- The agent's fixed fallback plan, used when Claude isn't available.

Every model can be turned off. With no API keys, CallGuard runs on mock transcription, rules only and the fixed agent plan. The evaluation in `backend/eval/` compares results with and without Claude.

## AI used to build CallGuard

**Claude Code** (Anthropic's coding assistant, running Claude Opus 5.5 in the terminal) was used throughout development.

How it was used:

- **Building to my plan:** I wrote `PLAN.md`, which sets out the stages, the stack and how I wanted to work. Claude Code built one stage at a time and stopped after each one for me to review.
- **Writing code and content:** it wrote the backend, frontend, call scripts, evaluation and documentation.
- **Testing:** it ran automated checks, played calls in Chrome through the Claude in Chrome extension, and ran the evaluation.
- **Research:** it read documentation pages, and checked the official phone numbers against government and organisation websites.

Decisions I made along the way:

- Having the browser stream the audio, so live microphone mode uses the same path as simulated calls.
- Switching transcription from Deepgram to ElevenLabs after Deepgram rejected my API keys.
- Using Claude instead of OpenAI for the LLM, and Claude Haiku 5.5 instead of Opus 5.5 for the agent, because it is faster during a live call.
- Hosting on Heroku and Netlify, after comparing options against my student credits.
- Fixes I asked for after reviewing behaviour, such as keeping whispers short, stopping summaries from claiming things the call didn't show, and silencing the recorded user when the agent takes over.

I reviewed each stage and ran and deployed the app myself.


// All frontend settings live here.

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8100";

// http:// becomes ws:// and https:// becomes wss://
export const WEBSOCKET_URL = `${BACKEND_URL.replace(/^http/, "ws")}/ws`;

export const RECONNECT_DELAY_MS = 2000;

// How often the browser sends the audio it has played so far to the backend.
export const AUDIO_SEND_INTERVAL_MS = 100;

// How loud the caller stays while a whisper or the agent is speaking.
export const CALLER_DUCK_LEVEL = 0.2;

// The audio format the backend expects from the microphone.
export const MIC_SAMPLE_RATE = 16000;

// A safety net in case the browser's built-in voice never reports finishing.
export const BROWSER_SPEECH_TIMEOUT_MS = 15000;

// How long a finished recording waits for the agent to complete a takeover.
export const AGENT_HOLD_LINE_MS = 20000;

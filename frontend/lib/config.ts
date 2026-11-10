// All frontend settings live here.

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8100";

// http:// becomes ws:// and https:// becomes wss://
export const WEBSOCKET_URL = `${BACKEND_URL.replace(/^http/, "ws")}/ws`;

export const RECONNECT_DELAY_MS = 2000;

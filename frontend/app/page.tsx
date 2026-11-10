"use client";

import { useEffect, useRef, useState } from "react";
import { BACKEND_URL, RECONNECT_DELAY_MS, WEBSOCKET_URL } from "../lib/config";

type SocketStatus = "connecting" | "connected" | "disconnected";

export default function Home() {
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("connecting");
  const [health, setHealth] = useState("checking");
  const [log, setLog] = useState<string[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  function addToLog(line: string) {
    const time = new Date().toLocaleTimeString();
    setLog((previous) => [`${time}  ${line}`, ...previous].slice(0, 20));
  }

  function sendPing() {
    socketRef.current?.send(
      JSON.stringify({ type: "ping", sent_at: performance.now() }),
    );
  }

  useEffect(() => {
    // Set on unmount so a socket we closed on purpose does not reconnect.
    let stopped = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    async function checkHealth() {
      try {
        const response = await fetch(`${BACKEND_URL}/health`);
        const body = await response.json();
        setHealth(body.status);
      } catch {
        setHealth("unreachable");
      }
    }

    function connect() {
      setSocketStatus("connecting");
      const socket = new WebSocket(WEBSOCKET_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        setSocketStatus("connected");
        checkHealth();
        sendPing();
      };

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "pong") {
          const roundTrip = performance.now() - message.sent_at;
          addToLog(`pong received in ${roundTrip.toFixed(1)} ms`);
        } else {
          addToLog(`received: ${event.data}`);
        }
      };

      socket.onclose = () => {
        if (stopped) return;
        setSocketStatus("disconnected");
        checkHealth();
        retryTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      socketRef.current?.close();
    };
  }, []);

  return (
    <main>
      <h1>CallGuard</h1>
      <p>
        Backend health: <strong id="health">{health}</strong>
      </p>
      <p>
        WebSocket: <strong id="socket-status">{socketStatus}</strong>
      </p>
      <button onClick={sendPing} disabled={socketStatus !== "connected"}>
        Send ping
      </button>
      <pre id="log">{log.join("\n")}</pre>
    </main>
  );
}

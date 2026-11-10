"use client";

import { useEffect, useRef, useState } from "react";
import { BACKEND_URL, RECONNECT_DELAY_MS, WEBSOCKET_URL } from "../lib/config";
import { playCall, type CallInfo } from "../lib/callPlayer";
import { Transcript, type Speaker, type TranscriptSegment } from "./Transcript";
import { RiskPanel, describeFindings, type RiskUpdate } from "./RiskPanel";

type SocketStatus = "connecting" | "connected" | "disconnected";
type CallStatus = "idle" | "loading" | "playing";

export default function Home() {
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("connecting");
  const [health, setHealth] = useState("checking");
  const [log, setLog] = useState<string[]>([]);
  const [calls, setCalls] = useState<CallInfo[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [secondsPlayed, setSecondsPlayed] = useState(0);
  const [secondsReceived, setSecondsReceived] = useState(0);
  const [transcriptionMode, setTranscriptionMode] = useState("not started");
  const [finals, setFinals] = useState<TranscriptSegment[]>([]);
  const [interim, setInterim] = useState<Partial<Record<Speaker, TranscriptSegment>>>({});
  const [risk, setRisk] = useState<RiskUpdate | null>(null);
  const [riskFindings, setRiskFindings] = useState<string[]>([]);
  const [llmMode, setLlmMode] = useState("not started");
  const socketRef = useRef<WebSocket | null>(null);
  const stopCallRef = useRef<(() => void) | null>(null);

  const selectedCall = calls.find((call) => call.id === selectedId);

  function addToLog(line: string) {
    const time = new Date().toLocaleTimeString();
    setLog((previous) => [`${time}  ${line}`, ...previous].slice(0, 20));
  }

  function sendPing() {
    socketRef.current?.send(
      JSON.stringify({ type: "ping", sent_at: performance.now() }),
    );
  }

  async function startCall() {
    if (!selectedCall || !socketRef.current) return;
    setCallStatus("loading");
    setSecondsPlayed(0);
    setSecondsReceived(0);
    setFinals([]);
    setInterim({});
    setRisk(null);
    setRiskFindings([]);
    try {
      stopCallRef.current = await playCall(
        selectedCall,
        socketRef.current,
        setSecondsPlayed,
        (reason) => {
          stopCallRef.current = null;
          setCallStatus("idle");
          addToLog(`call ended in browser: ${reason}`);
        },
      );
      setCallStatus("playing");
    } catch (error) {
      setCallStatus("idle");
      addToLog(`could not play call: ${error}`);
    }
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

    async function loadCalls() {
      try {
        const response = await fetch(`${BACKEND_URL}/calls`);
        const body: CallInfo[] = await response.json();
        setCalls(body);
        setSelectedId((current) => current || body[0]?.id || "");
      } catch {
        setCalls([]);
      }
    }

    function connect() {
      setSocketStatus("connecting");
      const socket = new WebSocket(WEBSOCKET_URL);
      socketRef.current = socket;

      socket.onopen = () => {
        setSocketStatus("connected");
        checkHealth();
        loadCalls();
        sendPing();
      };

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "pong") {
          const roundTrip = performance.now() - message.sent_at;
          addToLog(`pong received in ${roundTrip.toFixed(1)} ms`);
        } else if (message.type === "audio_progress") {
          setSecondsReceived(message.seconds_received);
        } else if (message.type === "transcript") {
          const segment: TranscriptSegment = message;
          // A final segment replaces that speaker's interim words.
          setInterim((previous) => ({
            ...previous,
            [segment.speaker]: segment.is_final ? undefined : segment,
          }));
          if (segment.is_final) {
            setFinals((previous) => [...previous, segment]);
          }
        } else if (message.type === "risk_update") {
          const update: RiskUpdate = message;
          setRisk(update);
          const findings = describeFindings(update);
          if (findings) {
            setRiskFindings((previous) => [findings, ...previous].slice(0, 12));
          }
        } else {
          if (message.type === "call_started") {
            setTranscriptionMode(message.transcription_mode);
            setLlmMode(message.llm_mode);
          }
          if (message.type === "call_ended") {
            setSecondsReceived(message.seconds_received);
            setInterim({});
          }
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
      stopCallRef.current?.();
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

      <h2>Simulated call</h2>
      <select
        id="call-picker"
        value={selectedId}
        onChange={(event) => setSelectedId(event.target.value)}
        disabled={callStatus !== "idle"}
      >
        {calls.map((call) => (
          <option key={call.id} value={call.id}>
            {call.title} ({Math.round(call.duration_seconds)}s)
          </option>
        ))}
      </select>{" "}
      {callStatus === "playing" ? (
        <button id="stop-call" onClick={() => stopCallRef.current?.()}>
          Stop
        </button>
      ) : (
        <button
          id="play-call"
          onClick={startCall}
          disabled={
            socketStatus !== "connected" ||
            !selectedCall ||
            callStatus === "loading"
          }
        >
          Play call
        </button>
      )}
      <p>
        Played in browser: <strong id="seconds-played">{secondsPlayed.toFixed(1)}s</strong>
      </p>
      <p>
        Received by backend: <strong id="seconds-received">{secondsReceived.toFixed(1)}s</strong>
      </p>

      <h2>Live transcript</h2>
      <p>
        Transcription: <strong id="transcription-mode">{transcriptionMode}</strong>
      </p>
      <Transcript finals={finals} interim={interim} />

      <h2>Call risk</h2>
      <RiskPanel risk={risk} findings={riskFindings} llmMode={llmMode} />

      <h2>Log</h2>
      <pre id="log">{log.join("\n")}</pre>
    </main>
  );
}

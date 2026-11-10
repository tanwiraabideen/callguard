"use client";

// All of the page's call state, and the handling of messages from the backend.

import { useEffect, useRef, useState } from "react";
import {
  CALLER_DUCK_LEVEL,
  BACKEND_URL,
  RECONNECT_DELAY_MS,
  WEBSOCKET_URL,
} from "../lib/config";
import {
  playCall,
  type CallController,
  type CallInfo,
  type EndReason,
} from "../lib/callPlayer";
import { startMicCall } from "../lib/micCall";
import { SpeechPlayer, type SpeechMessage } from "../lib/speechPlayer";
import type { Alert } from "./AlertList";
import type { RiskPoint } from "./RiskChart";
import type { RiskUpdate } from "./RiskPanel";
import type { CallSummary } from "./SummaryCard";
import type { TraceEntry } from "./TracePanel";
import type { Speaker, TranscriptSegment } from "./Transcript";

type SocketStatus = "connecting" | "connected" | "disconnected";
type CallStatus = "idle" | "loading" | "playing";
type Interim = Partial<Record<Speaker, TranscriptSegment>>;

export function useCall() {
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("connecting");
  const [health, setHealth] = useState("checking");
  const [log, setLog] = useState<string[]>([]);
  const [calls, setCalls] = useState<CallInfo[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [isLive, setIsLive] = useState(false);
  const [secondsPlayed, setSecondsPlayed] = useState(0);
  const [secondsReceived, setSecondsReceived] = useState(0);
  const [maxSeconds, setMaxSeconds] = useState<number | null>(null);
  const [transcriptionMode, setTranscriptionMode] = useState("not started");
  const [llmMode, setLlmMode] = useState("not started");
  const [agentMode, setAgentMode] = useState("not started");
  const [finals, setFinals] = useState<TranscriptSegment[]>([]);
  const [interim, setInterim] = useState<Interim>({});
  const [risk, setRisk] = useState<RiskUpdate | null>(null);
  const [riskPoints, setRiskPoints] = useState<RiskPoint[]>([]);
  const [thresholds, setThresholds] = useState({ medium: 40, high: 70 });
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [trace, setTrace] = useState<TraceEntry[]>([]);
  const [summary, setSummary] = useState<CallSummary | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const controllerRef = useRef<CallController | null>(null);
  const speechRef = useRef<SpeechPlayer | null>(null);
  const secondsPlayedRef = useRef(0);
  const speakingAsUserRef = useRef(false);
  const agentTakingOverRef = useRef(false);

  function addToLog(line: string) {
    const time = new Date().toLocaleTimeString();
    setLog((previous) => [`${time}  ${line}`, ...previous].slice(0, 20));
  }

  function sendPing() {
    socketRef.current?.send(
      JSON.stringify({ type: "ping", sent_at: performance.now() }),
    );
  }

  function updatePlayed(seconds: number) {
    secondsPlayedRef.current = seconds;
    setSecondsPlayed(seconds);
  }

  function resetForNewCall(live: boolean) {
    setCallStatus("loading");
    setIsLive(live);
    updatePlayed(0);
    agentTakingOverRef.current = false;
    setSecondsReceived(0);
    setFinals([]);
    setInterim({});
    setRisk(null);
    setRiskPoints([]);
    setAlerts([]);
    setTrace([]);
    setSummary(null);
    speechRef.current = new SpeechPlayer(
      () => controllerRef.current?.setCallerLevel(CALLER_DUCK_LEVEL),
      () => controllerRef.current?.setCallerLevel(1),
    );
  }

  function handleCallEnded(reason: EndReason) {
    controllerRef.current = null;
    setCallStatus("idle");
    addToLog(`call ended in browser: ${reason}`);
    const speech = speechRef.current;
    speechRef.current = null;
    speech?.whenIdle().then(() => speech.close());
  }

  async function startCall(start: () => Promise<CallController>, live: boolean) {
    resetForNewCall(live);
    try {
      controllerRef.current = await start();
      setCallStatus("playing");
    } catch (error) {
      setCallStatus("idle");
      addToLog(`could not start the call: ${error}`);
    }
  }

  function playSelectedCall() {
    const call = calls.find((item) => item.id === selectedId);
    const socket = socketRef.current;
    if (call && socket) {
      startCall(
        () =>
          playCall(
            call,
            socket,
            updatePlayed,
            handleCallEnded,
            () => agentTakingOverRef.current,
          ),
        false,
      );
    }
  }

  function startLiveCall() {
    const socket = socketRef.current;
    if (socket) {
      startCall(
        () =>
          startMicCall(
            socket,
            () => speakingAsUserRef.current,
            updatePlayed,
            handleCallEnded,
          ),
        true,
      );
    }
  }

  function stopCall() {
    controllerRef.current?.stop("stopped");
  }

  function dismissAlert(id: number) {
    socketRef.current?.send(JSON.stringify({ type: "dismiss_alert", alert_id: id }));
  }

  function setSpeakingAsUser(speaking: boolean) {
    speakingAsUserRef.current = speaking;
  }

  function handleSpeech(message: SpeechMessage) {
    speechRef.current?.enqueue(message);
    const now = secondsPlayedRef.current;
    setFinals((previous) => [
      ...previous,
      {
        speaker: message.kind === "whisper" ? "whisper" : "agent",
        text: message.text,
        start: now,
        end: now,
        is_final: true,
      },
    ]);
  }

  function handleMessage(raw: string) {
    const message = JSON.parse(raw);
    switch (message.type) {
      case "pong": {
        const roundTrip = performance.now() - message.sent_at;
        addToLog(`pong received in ${roundTrip.toFixed(1)} ms`);
        break;
      }
      case "audio_progress":
        setSecondsReceived(message.seconds_received);
        break;
      case "transcript": {
        const segment: TranscriptSegment = message;
        // A final segment replaces that speaker's interim words.
        setInterim((previous) => ({
          ...previous,
          [segment.speaker]: segment.is_final ? undefined : segment,
        }));
        if (segment.is_final) {
          setFinals((previous) => [...previous, segment]);
        }
        break;
      }
      case "risk_update": {
        const update: RiskUpdate = message;
        setRisk(update);
        setRiskPoints((previous) => [
          ...previous,
          { time: update.time, score: update.score },
        ]);
        break;
      }
      case "alert":
        setAlerts((previous) => [...previous, message]);
        break;
      case "alert_dismissed":
        setAlerts((previous) =>
          previous.map((alert) =>
            alert.id === message.alert_id ? { ...alert, dismissed: true } : alert,
          ),
        );
        break;
      case "trace":
        setTrace((previous) => [...previous, message]);
        if (message.event === "agent_start" && message.mode === "take_over") {
          agentTakingOverRef.current = true;
        }
        break;
      case "speech":
        handleSpeech(message);
        break;
      case "agent_end_call": {
        // Let the agent finish speaking before the line goes dead.
        const finished = speechRef.current?.whenIdle() ?? Promise.resolve();
        finished.then(() => controllerRef.current?.stop("agent_ended"));
        break;
      }
      case "call_limit_reached":
        controllerRef.current?.stop("call_limit");
        addToLog("this call reached its time limit");
        break;
      case "call_summary":
        setSummary(message);
        break;
      case "call_started":
        setTranscriptionMode(message.transcription_mode);
        setLlmMode(message.llm_mode);
        setAgentMode(message.agent_mode);
        setMaxSeconds(message.max_seconds);
        setThresholds({
          medium: message.medium_threshold,
          high: message.high_threshold,
        });
        addToLog(`received: ${raw}`);
        break;
      case "call_ended":
        setSecondsReceived(message.seconds_received);
        setInterim({});
        addToLog(`received: ${raw}`);
        break;
      default:
        addToLog(`received: ${raw}`);
    }
  }

  // The socket's handlers are set once, so they call the latest handler this way.
  const handleMessageRef = useRef(handleMessage);
  useEffect(() => {
    handleMessageRef.current = handleMessage;
  });

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
        socket.send(JSON.stringify({ type: "ping", sent_at: performance.now() }));
      };

      socket.onmessage = (event) => handleMessageRef.current(event.data);

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
      controllerRef.current?.stop("stopped");
      socketRef.current?.close();
    };
  }, []);

  return {
    socketStatus,
    health,
    log,
    calls,
    selectedId,
    setSelectedId,
    callStatus,
    isLive,
    secondsPlayed,
    secondsReceived,
    maxSeconds,
    transcriptionMode,
    llmMode,
    agentMode,
    finals,
    interim,
    risk,
    riskPoints,
    thresholds,
    alerts,
    trace,
    summary,
    sendPing,
    playSelectedCall,
    startLiveCall,
    stopCall,
    dismissAlert,
    setSpeakingAsUser,
  };
}

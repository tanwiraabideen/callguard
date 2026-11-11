"use client";

import { AlertList } from "./AlertList";
import { PasscodeForm } from "./PasscodeForm";
import { RiskChart } from "./RiskChart";
import { RiskPanel } from "./RiskPanel";
import { SummaryCard } from "./SummaryCard";
import { TracePanel } from "./TracePanel";
import { Transcript } from "./Transcript";
import { useCall } from "./useCall";

export default function Home() {
  const call = useCall();
  const isIdle = call.callStatus === "idle";
  const isConnected = call.socketStatus === "connected";

  if (call.needsPasscode) {
    return <PasscodeForm error={call.passcodeError} onSubmit={call.submitPasscode} />;
  }

  return (
    <main style={{ display: "flex", flexWrap: "wrap", gap: 32 }}>
      <div style={{ flex: "1 1 480px", minWidth: 0 }}>
        <h1>CallGuard</h1>
        <p>
          Backend health: <strong id="health">{call.health}</strong>. WebSocket:{" "}
          <strong id="socket-status">{call.socketStatus}</strong>{" "}
          <button onClick={call.sendPing} disabled={!isConnected}>
            Send ping
          </button>
        </p>

        <h2>Call</h2>
        <select
          id="call-picker"
          value={call.selectedId}
          onChange={(event) => call.setSelectedId(event.target.value)}
          disabled={!isIdle}
          style={{ maxWidth: "100%" }}
        >
          {call.calls.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title} ({Math.round(item.duration_seconds)}s)
            </option>
          ))}
        </select>{" "}
        {call.callStatus === "playing" ? (
          <button id="stop-call" onClick={call.stopCall}>
            Stop
          </button>
        ) : (
          <>
            <button
              id="play-call"
              onClick={call.playSelectedCall}
              disabled={!isConnected || !call.selectedId || !isIdle}
            >
              Play call
            </button>{" "}
            <button id="live-call" onClick={call.startLiveCall} disabled={!isConnected || !isIdle}>
              Try to scam me (microphone)
            </button>
          </>
        )}

        {call.isLive && call.callStatus === "playing" && (
          <p>
            Mic level:{" "}
            <span
              style={{ display: "inline-block", width: 160, height: 10, background: "lightgray" }}
            >
              <span
                id="mic-level"
                style={{
                  display: "block",
                  height: "100%",
                  width: `${Math.min(100, call.micLevel * 100)}%`,
                  background: "seagreen",
                }}
              />
            </span>{" "}
            {call.micLevel < 0.01 ? "No sound from your microphone" : ""}
          </p>
        )}

        {call.isLive && call.callStatus === "playing" && (
          <p>
            You are the caller. To answer as the person being scammed, for example to say
            &quot;let me grab a pen&quot;:{" "}
            <button
              id="speak-as-user"
              onPointerDown={() => call.setSpeakingAsUser(true)}
              onPointerUp={() => call.setSpeakingAsUser(false)}
              onPointerLeave={() => call.setSpeakingAsUser(false)}
            >
              Hold to speak as the user
            </button>
          </p>
        )}

        <p>
          {call.isLive ? "Microphone" : "Played in browser"}:{" "}
          <strong id="seconds-played">{call.secondsPlayed.toFixed(1)}s</strong>
          {call.isLive && call.maxSeconds ? ` of ${call.maxSeconds}s` : ""}. Received by backend:{" "}
          <strong id="seconds-received">{call.secondsReceived.toFixed(1)}s</strong>.
          Transcription: <strong id="transcription-mode">{call.transcriptionMode}</strong>
        </p>

        <h2>Alerts</h2>
        <AlertList alerts={call.alerts} onDismiss={call.dismissAlert} />

        <h2>Live transcript</h2>
        <Transcript finals={call.finals} interim={call.interim} />

        <h2>Call risk</h2>
        <RiskPanel risk={call.risk} llmMode={call.llmMode} agentMode={call.agentMode} />
        <RiskChart points={call.riskPoints} thresholds={call.thresholds} />

        {call.summary && <SummaryCard summary={call.summary} />}

        <h2>Log</h2>
        <pre id="log" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
          {call.log.join("\n")}
        </pre>
      </div>

      <div style={{ flex: "1 1 360px", minWidth: 0 }}>
        <h2>Behind the scenes</h2>
        <TracePanel entries={call.trace} />
      </div>
    </main>
  );
}

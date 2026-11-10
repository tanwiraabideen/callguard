export type RiskFinding = { label: string; suppressed?: boolean };

export type RiskUpdate = {
  source: "sentence" | "llm" | "dismissal";
  time: number;
  score: number;
  level: "low" | "medium" | "high";
  reason: string;
  rules: RiskFinding[];
  pressure: RiskFinding[];
};

const LEVEL_COLOURS = {
  low: "seagreen",
  medium: "darkorange",
  high: "crimson",
};

export function RiskPanel({
  risk,
  llmMode,
  agentMode,
}: {
  risk: RiskUpdate | null;
  llmMode: string;
  agentMode: string;
}) {
  const score = risk?.score ?? 0;
  const level = risk?.level ?? "low";

  return (
    <div>
      <p>
        Risk: <strong id="risk-score">{Math.round(score)}</strong> / 100{" "}
        <strong id="risk-level" style={{ color: LEVEL_COLOURS[level] }}>
          {level.toUpperCase()}
        </strong>
      </p>
      <div style={{ height: 12, background: "lightgray", maxWidth: 400 }}>
        <div
          style={{
            height: "100%",
            width: `${score}%`,
            background: LEVEL_COLOURS[level],
            transition: "width 0.4s",
          }}
        />
      </div>
      <p>
        Reason: <span id="risk-reason">{risk?.reason ?? "No call yet"}</span>
      </p>
      <p>
        LLM check: <strong id="llm-mode">{llmMode}</strong>. Agent:{" "}
        <strong id="agent-mode">{agentMode}</strong>
      </p>
    </div>
  );
}

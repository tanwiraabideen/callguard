export type RiskFinding = { label: string };

export type RiskUpdate = {
  source: "sentence" | "llm";
  time: number;
  score: number;
  level: "low" | "medium" | "high";
  reason: string;
  rules: RiskFinding[];
  pressure: RiskFinding[];
  llm: { score: number; reason: string; latency_ms: number; model: string } | null;
};

const LEVEL_COLOURS = {
  low: "seagreen",
  medium: "darkorange",
  high: "crimson",
};

export function describeFindings(update: RiskUpdate): string | null {
  const time = `${update.time.toFixed(1)}s`;
  if (update.llm) {
    const { score, model, latency_ms: latency } = update.llm;
    return `${time}  LLM scored ${score} (${model}, ${latency} ms)`;
  }
  const findings = [...update.rules, ...update.pressure].map((item) => item.label);
  return findings.length > 0 ? `${time}  ${findings.join("; ")}` : null;
}

export function RiskPanel({
  risk,
  findings,
  llmMode,
}: {
  risk: RiskUpdate | null;
  findings: string[];
  llmMode: string;
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
        LLM check: <strong id="llm-mode">{llmMode}</strong>
      </p>
      <pre id="risk-findings">{findings.join("\n")}</pre>
    </div>
  );
}

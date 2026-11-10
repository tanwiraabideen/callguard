// The "behind the scenes" panel: every decision the system made, newest first.

export type TraceEntry = {
  event: string;
  time: number;
  [key: string]: unknown;
};

type Finding = { label: string; matched?: string; suppressed?: boolean; value?: number };

function describeFindings(entry: TraceEntry): string {
  const rules = (entry.rules as Finding[]).map(
    (rule) => `rule: ${rule.label} ("${rule.matched}")${rule.suppressed ? " [dismissed]" : ""}`,
  );
  const pressure = (entry.pressure as Finding[]).map(
    (signal) => `pressure: ${signal.label} (${signal.value})`,
  );
  return [...rules, ...pressure].join("; ");
}

function describe(entry: TraceEntry): { title: string; detail?: string } {
  switch (entry.event) {
    case "sentence":
      return {
        title: `${entry.speaker}: ${entry.text}`,
        detail: `${describeFindings(entry) || "nothing fired"}. Score ${entry.score}. Checked in ${entry.check_ms} ms`,
      };
    case "llm":
      return {
        title: `LLM ${entry.model}, ${entry.latency_ms} ms`,
        detail: String(entry.raw),
      };
    case "llm_error":
      return { title: "LLM check failed", detail: String(entry.detail) };
    case "alert":
      return {
        title: `Alert #${entry.id}: ${entry.level}${entry.is_realert ? " (re-alert)" : ""}`,
        detail: `${entry.reason}${entry.whisper ? `. Whisper: ${entry.whisper}` : ""}`,
      };
    case "dismissal":
      return {
        title: `Dismissed alert #${entry.alert_id}`,
        detail: `Lowered: ${(entry.categories as string[]).join(", ")}`,
      };
    case "trigger":
      return { title: `Trigger phrase #${entry.count}: "${entry.phrase}"` };
    case "agent_start":
      return { title: `Agent started: ${entry.mode}`, detail: String(entry.reason) };
    case "agent_decision":
      return {
        title: `Agent decided: ${(entry.tools as string[]).join(", ") || "finish"}`,
        detail: `By ${entry.decided_by}${entry.latency_ms ? `, ${entry.latency_ms} ms` : ""}`,
      };
    case "tool":
      return {
        title: `Tool ${entry.name}, ${entry.latency_ms} ms`,
        detail: `in: ${JSON.stringify(entry.input)}\nout: ${JSON.stringify(entry.output)}`,
      };
    case "agent_done":
      return { title: `Agent finished: ${entry.mode}` };
    case "agent_step_limit":
      return { title: `Agent stopped at its step limit (${entry.steps})` };
    case "agent_error":
      return { title: "Agent error", detail: String(entry.detail) };
    default:
      return { title: entry.event };
  }
}

export function TracePanel({ entries }: { entries: TraceEntry[] }) {
  const langsmithUrl = entries.find((entry) => entry.langsmith_url)?.langsmith_url as
    | string
    | undefined;

  return (
    <div>
      <p>
        LangSmith:{" "}
        {langsmithUrl ? (
          <a id="langsmith-link" href={langsmithUrl} target="_blank" rel="noreferrer">
            open the agent trace
          </a>
        ) : (
          <span id="langsmith-link">no trace for this run</span>
        )}
      </p>
      <div
        id="trace"
        style={{ height: 620, overflowY: "auto", border: "1px solid gray", padding: 8 }}
      >
        {[...entries].reverse().map((entry, index) => {
          const { title, detail } = describe(entry);
          return (
            <div key={index} className="trace-entry" style={{ marginBottom: 8, fontSize: 13 }}>
              <small>{entry.time.toFixed(1)}s</small> <strong>{title}</strong>
              {detail && (
                <div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", color: "#555" }}>
                  {detail}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

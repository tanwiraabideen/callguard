export type CallSummary = {
  title: string;
  ended_by: string;
  seconds: number;
  peak_score: number;
  peak_level: string;
  what_happened: string;
  red_flags: { label: string; first_time: number; count: number }[];
  dismissed: { alert_id: number; categories: string[]; time: number }[];
  agent_actions: string[];
  next_steps: string[];
  langsmith_url: string | null;
};

export function SummaryCard({ summary }: { summary: CallSummary }) {
  return (
    <div id="summary" style={{ border: "2px solid gray", padding: 12, marginTop: 12 }}>
      <h2 style={{ marginTop: 0 }}>After the call: {summary.title}</h2>
      <p>{summary.what_happened}</p>
      <p>
        Lasted {summary.seconds.toFixed(0)}s, ended by {summary.ended_by}. Peak risk{" "}
        {Math.round(summary.peak_score)} ({summary.peak_level}).
      </p>

      <h3>Warning signs</h3>
      {summary.red_flags.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {summary.red_flags.map((flag) => (
            <li key={flag.label}>
              {flag.label}: first at {flag.first_time.toFixed(1)}s, {flag.count} time
              {flag.count === 1 ? "" : "s"}
            </li>
          ))}
        </ul>
      )}

      <h3>Dismissed alerts</h3>
      {summary.dismissed.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {summary.dismissed.map((item) => (
            <li key={item.alert_id}>
              Alert #{item.alert_id} at {item.time.toFixed(1)}s: {item.categories.join(", ")}
            </li>
          ))}
        </ul>
      )}

      {summary.agent_actions.length > 0 && (
        <p>Agent actions: {summary.agent_actions.join(", ")}</p>
      )}

      <h3>What to do next</h3>
      <ul>
        {summary.next_steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>

      {summary.langsmith_url && (
        <a href={summary.langsmith_url} target="_blank" rel="noreferrer">
          Open the agent trace in LangSmith
        </a>
      )}
    </div>
  );
}

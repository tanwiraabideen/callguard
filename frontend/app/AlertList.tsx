export type Alert = {
  id: number;
  level: "medium" | "high";
  reason: string;
  time: number;
  is_realert: boolean;
  whisper: string | null;
  dismissed?: boolean;
};

export function AlertList({
  alerts,
  onDismiss,
}: {
  alerts: Alert[];
  onDismiss: (id: number) => void;
}) {
  if (alerts.length === 0) return <p>No alerts.</p>;

  return (
    <div id="alerts">
      {[...alerts].reverse().map((alert) => (
        <div
          key={alert.id}
          className="alert"
          style={{
            border: `2px solid ${alert.level === "high" ? "crimson" : "darkorange"}`,
            opacity: alert.dismissed ? 0.5 : 1,
            padding: 8,
            margin: "8px 0",
          }}
        >
          <strong>
            {alert.level === "high" ? "High risk" : "Be careful"}
            {alert.is_realert ? " (new warning sign)" : ""}
          </strong>{" "}
          <small>at {alert.time.toFixed(1)}s</small>
          <div>{alert.reason}</div>
          {alert.dismissed ? (
            <small>Dismissed</small>
          ) : (
            <button className="dismiss-alert" onClick={() => onDismiss(alert.id)}>
              Not a scam
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

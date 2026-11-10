import { useState } from "react";

export type RiskPoint = { time: number; score: number };

const WIDTH = 480;
const HEIGHT = 140;
const LEFT = 28;
const RIGHT = 8;
const TOP = 8;
const BOTTOM = 20;
const INK = "#6b6b6b";

export function RiskChart({
  points,
  thresholds,
}: {
  points: RiskPoint[];
  thresholds: { medium: number; high: number };
}) {
  const [hovered, setHovered] = useState<RiskPoint | null>(null);

  const maxTime = Math.max(30, ...points.map((point) => point.time));
  const x = (time: number) => LEFT + (time / maxTime) * (WIDTH - LEFT - RIGHT);
  const y = (score: number) => TOP + (1 - score / 100) * (HEIGHT - TOP - BOTTOM);
  const line = points.map((point) => `${x(point.time)},${y(point.score)}`).join(" ");

  function showNearest(event: React.MouseEvent<SVGSVGElement>) {
    if (points.length === 0) return;
    const box = event.currentTarget.getBoundingClientRect();
    const mouseX = ((event.clientX - box.left) / box.width) * WIDTH;
    const nearest = points.reduce((best, point) =>
      Math.abs(x(point.time) - mouseX) < Math.abs(x(best.time) - mouseX) ? point : best,
    );
    setHovered(nearest);
  }

  return (
    <div>
      <svg
        id="risk-chart"
        role="img"
        aria-label="Call risk score over the call"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", maxWidth: WIDTH }}
        onMouseMove={showNearest}
        onMouseLeave={() => setHovered(null)}
      >
        <text x={LEFT - 4} y={y(100) + 8} textAnchor="end" fontSize={10} fill={INK}>
          100
        </text>
        <text x={LEFT - 4} y={y(0)} textAnchor="end" fontSize={10} fill={INK}>
          0
        </text>
        <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(0)} y2={y(0)} stroke={INK} strokeWidth={1} />
        <text x={WIDTH - RIGHT} y={HEIGHT - 6} textAnchor="end" fontSize={10} fill={INK}>
          {Math.round(maxTime)}s
        </text>

        {[
          { label: "medium", value: thresholds.medium },
          { label: "high", value: thresholds.high },
        ].map(({ label, value }) => (
          <g key={label}>
            <line
              x1={LEFT}
              x2={WIDTH - RIGHT}
              y1={y(value)}
              y2={y(value)}
              stroke={INK}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <text x={LEFT + 4} y={y(value) - 3} fontSize={10} fill={INK}>
              {label}
            </text>
          </g>
        ))}

        <polyline
          points={line}
          fill="none"
          stroke="#2a78c7"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {hovered && (
          <>
            <line
              x1={x(hovered.time)}
              x2={x(hovered.time)}
              y1={TOP}
              y2={y(0)}
              stroke={INK}
              strokeWidth={1}
            />
            <circle
              cx={x(hovered.time)}
              cy={y(hovered.score)}
              r={4}
              fill="#2a78c7"
              stroke="white"
              strokeWidth={2}
            />
          </>
        )}
      </svg>
      <div style={{ minHeight: 18 }}>
        <small>
          {hovered
            ? `${hovered.time.toFixed(1)}s: risk ${Math.round(hovered.score)}`
            : "Hover over the chart to read a value."}
        </small>
      </div>
    </div>
  );
}

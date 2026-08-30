"use client";

import { useState } from "react";
import type { EquityPoint } from "@/lib/types";

const ranges = { "1W": 7, "1M": 31, ALL: Number.POSITIVE_INFINITY } as const;

export function EquityChart({ points }: { points: EquityPoint[] }) {
  const [range, setRange] = useState<keyof typeof ranges>("1M");
  const visible = points.slice(-ranges[range]);
  const width = 860;
  const height = 270;
  const values = visible.map((point) => point.equity);
  const min = Math.min(...values) * 0.998;
  const max = Math.max(...values) * 1.002;
  const span = Math.max(max - min, 1);
  const coords = visible.map((point, index) => [8 + (index / Math.max(visible.length - 1, 1)) * (width - 16), 8 + ((max - point.equity) / span) * (height - 24)] as const);
  const line = coords.map(([x, y], index) => `${index ? "L" : "M"}${x},${y}`).join(" ");
  const area = `${line} L${width - 8},${height} L8,${height} Z`;
  const change = (visible.at(-1)?.equity ?? 0) - (visible.at(0)?.equity ?? 0);
  return (
    <div className="equity-chart-wrap">
      <div className="chart-toolbar"><div><span>Selected period</span><strong className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}${change.toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong></div><div className="range-tabs" aria-label="Performance range">{Object.keys(ranges).map((item) => <button key={item} type="button" aria-pressed={range === item} className={range === item ? "active" : ""} onClick={() => setRange(item as keyof typeof ranges)}>{item}</button>)}</div></div>
      <svg className="equity-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Paper equity performance, ${change >= 0 ? "up" : "down"} ${Math.abs(change).toFixed(2)} dollars over the selected range`}>
        <defs><linearGradient id="equity-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".28" /><stop offset="100%" stopColor="var(--accent)" stopOpacity="0" /></linearGradient></defs>
        {[.25, .5, .75].map((ratio) => <line key={ratio} x1="0" x2={width} y1={height * ratio} y2={height * ratio} className="chart-gridline" />)}
        <path d={area} fill="url(#equity-fill)" /><path d={line} className="chart-line" />{coords.length > 0 && <circle cx={coords.at(-1)?.[0]} cy={coords.at(-1)?.[1]} r="5" className="chart-point" />}
      </svg>
      <details className="accessible-data"><summary>View performance data</summary><table><thead><tr><th>Date</th><th>Equity</th><th>P&amp;L</th></tr></thead><tbody>{visible.slice(-7).map((point) => <tr key={point.timestamp}><td>{new Date(point.timestamp).toLocaleDateString()}</td><td>${point.equity.toLocaleString()}</td><td>${point.profit_loss.toLocaleString()}</td></tr>)}</tbody></table></details>
    </div>
  );
}

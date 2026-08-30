import type { PricePoint } from "@/lib/types";

export function PriceChart({ prices, symbol }: { prices: PricePoint[]; symbol: string }) {
  const width = 760;
  const height = 250;
  const padding = 10;
  const visible = prices.slice(-64);
  const values = visible.map((point) => point.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const coordinates = visible.map((point, index) => {
    const x = padding + (index / Math.max(visible.length - 1, 1)) * (width - padding * 2);
    const y = padding + ((max - point.close) / span) * (height - padding * 2);
    return [x, y] as const;
  });
  const line = coordinates.map(([x, y], index) => `${index ? "L" : "M"}${x},${y}`).join(" ");
  const area = `${line} L${width - padding},${height} L${padding},${height} Z`;
  const first = visible.at(0)?.close ?? 0;
  const last = visible.at(-1)?.close ?? 0;
  const trend = last >= first ? "up" : "down";

  return (
    <div className="chart-wrap">
      <svg
        className="price-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby="chart-title chart-description"
      >
        <title id="chart-title">{symbol} closing-price history</title>
        <desc id="chart-description">
          {visible.length} observations ranging from ${min.toFixed(2)} to ${max.toFixed(2)},
          ending {trend} at ${last.toFixed(2)}.
        </desc>
        <defs>
          <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((ratio) => (
          <line
            key={ratio}
            x1="0"
            x2={width}
            y1={height * ratio}
            y2={height * ratio}
            className="chart-gridline"
          />
        ))}
        <path d={area} fill="url(#chart-fill)" />
        <path d={line} className="chart-line" />
        {coordinates.length > 0 && (
          <circle
            cx={coordinates.at(-1)?.[0]}
            cy={coordinates.at(-1)?.[1]}
            r="5"
            className="chart-point"
          />
        )}
      </svg>
      <div className="chart-axis" aria-hidden="true">
        <span>${min.toFixed(2)}</span>
        <span>64 sessions</span>
        <span>${max.toFixed(2)}</span>
      </div>
      <details className="accessible-data">
        <summary>View recent price data</summary>
        <table>
          <thead><tr><th>Date</th><th>Close</th><th>Volume</th></tr></thead>
          <tbody>
            {visible.slice(-5).map((point) => (
              <tr key={point.timestamp}>
                <td>{new Date(point.timestamp).toLocaleDateString()}</td>
                <td>${point.close.toFixed(2)}</td>
                <td>{point.volume.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}


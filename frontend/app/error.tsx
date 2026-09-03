"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="data-error-shell">
      <div className="data-error-card">
        <span className="icon-tile"><AlertTriangle size={21} aria-hidden="true" /></span>
        <p className="eyebrow">Live data required</p>
        <h1>Alpaca data is unavailable</h1>
        <p>RegimeShift never substitutes demo prices, positions, orders, or signals. Check the Alpaca connection and try again.</p>
        <button type="button" className="primary-action" onClick={reset}><RefreshCw size={16} aria-hidden="true" /> Retry live connection</button>
      </div>
    </main>
  );
}

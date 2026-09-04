#!/usr/bin/env python3
"""Backtest the 15-minute scanner before its execution gate can open."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE  # noqa: E402
from regimeshift.domain.scanner_backtest import IntradayScannerBacktester  # noqa: E402
from regimeshift.services.market_data import AlpacaMarketDataProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    provider = AlpacaMarketDataProvider(Settings(market_data_mode="alpaca"))
    symbols = ["SPY", *LARGE_CAP_UNIVERSE]
    histories = provider.get_intraday_history(symbols, days=args.days, bar_minutes=15)
    liquidity = provider.get_price_history(symbols, days=args.days + 45)
    report = IntradayScannerBacktester().evaluate(histories, liquidity)
    report.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "Alpaca IEX fully adjusted 15-minute bars",
            "history": {
                "calendar_days_requested": args.days,
                "benchmark_bars": len(histories["SPY"]),
                "start": histories["SPY"][0].timestamp.isoformat(),
                "end": histories["SPY"][-1].timestamp.isoformat(),
            },
        }
    )
    payload = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return (
        0
        if report["production_gate_passed"] or report["exploration_gate_passed"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())

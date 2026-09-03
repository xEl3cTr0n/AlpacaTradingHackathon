#!/usr/bin/env python3
"""Reproducible walk-forward validation for the swing/voting policy."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402
from regimeshift.domain.backtest import BacktestParameters, SwingVoteBacktester  # noqa: E402
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE  # noqa: E402
from regimeshift.services.market_data import (  # noqa: E402
    AlpacaMarketDataProvider,
    DemoMarketDataProvider,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1825, help="Calendar days of history")
    parser.add_argument("--demo", action="store_true", help="Use deterministic demo bars")
    args = parser.parse_args()

    settings = Settings(market_data_mode="demo" if args.demo else "alpaca")
    provider = (
        DemoMarketDataProvider() if args.demo else AlpacaMarketDataProvider(settings)
    )
    symbols = ["SPY", "DIA", *SECTOR_UNIVERSE]
    histories = provider.get_price_history(symbols, days=args.days)
    backtester = SwingVoteBacktester()
    report = backtester.tune(histories)
    selected = BacktestParameters(**report["parameters"])
    confirmation = backtester.evaluate(histories, selected, "DIA")
    report["cross_asset_confirmation"] = {
        "instrument": "DIA directional proxy for DJX defined-risk spreads",
        **confirmation,
    }
    report["approved_scope"] = ["SPY signal → XSP defined-risk spreads"]
    report["rejected_scope"] = (
        []
        if float(confirmation["total_return"]) > 0
        else ["DIA signal → DJX spreads failed cross-asset confirmation"]
    )
    report.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "source": "deterministic demo tape" if args.demo else "Alpaca IEX adjusted daily bars",
            "history": {
                "calendar_days_requested": args.days,
                "benchmark_bars": len(histories["SPY"]),
                "start": histories["SPY"][0].timestamp.isoformat(),
                "end": histories["SPY"][-1].timestamp.isoformat(),
            },
        }
    )
    print(json.dumps(report, indent=2))
    return 0 if report["production_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

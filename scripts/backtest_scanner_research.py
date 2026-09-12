#!/usr/bin/env python3
"""Read-only Alpaca research backtest. Writes aggregate metrics, never source bars or orders."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE  # noqa: E402
from regimeshift.domain.scanner_research_backtest import evaluate_research  # noqa: E402
from regimeshift.services.market_data import AlpacaMarketDataProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1825)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    now = datetime.now(UTC)
    histories = AlpacaMarketDataProvider(Settings(market_data_mode="alpaca")).get_price_history(
        list(LARGE_CAP_UNIVERSE), days=args.days,
    )
    result = evaluate_research(histories, now)
    result["generated_at"] = now.isoformat()
    result["calendar_days_requested"] = args.days
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()

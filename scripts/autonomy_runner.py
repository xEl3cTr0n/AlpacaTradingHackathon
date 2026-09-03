#!/usr/bin/env python3
"""Run the voting agent and prepare or submit one gated XSP paper spread."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402
from regimeshift.domain.models import AnalysisControls, InstrumentMode  # noqa: E402
from regimeshift.orchestration.pipeline import DecisionPipeline  # noqa: E402
from regimeshift.services.alpaca_cli import AlpacaCliAdapter  # noqa: E402
from regimeshift.services.market_data import AlpacaMarketDataProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--target-dte", type=int, default=30)
    args = parser.parse_args()

    settings = Settings(market_data_mode="alpaca", alpaca_cli_enabled=True)
    market_data = AlpacaMarketDataProvider(settings)
    snapshot = DecisionPipeline(settings, market_data).analyze(
        args.symbol.upper(),
        AnalysisControls(
            instrument_mode=InstrumentMode.INDEX_OPTION,
            target_dte=args.target_dte,
        ),
    )
    summary: dict[str, object] = {
        "decision_id": snapshot.decision_id,
        "signal": snapshot.swing.signal,
        "council": {
            "approved": snapshot.council.approved,
            "support": snapshot.council.support_count,
            "oppose": snapshot.council.oppose_count,
            "weighted_support": snapshot.council.weighted_support,
        },
        "risk": {
            "approved": snapshot.risk.approved,
            "reasons": snapshot.risk.reasons,
        },
        "strategy": snapshot.strategy.display_name,
    }
    if not snapshot.risk.approved:
        summary["execution"] = {"status": "no_trade", "paper_only": True}
        print(json.dumps(summary, indent=2, default=str))
        return 0

    cli = AlpacaCliAdapter(settings)
    plan = cli.prepare_index_spread(snapshot)
    result = cli.submit_or_preview(snapshot, plan, execute=args.execute)
    summary["cli"] = cli.verify()
    summary["plan"] = {
        key: value
        for key, value in plan.items()
        if key not in {"legs"}
    }
    summary["execution"] = {
        "status": result["status"],
        "allowed": result["allowed"],
        "paper_only": result["paper_only"],
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Scan liquid large caps and preview/submit the strongest gated paper trade."""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".scanner-state.json"
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402
from regimeshift.domain.models import AnalysisControls, InstrumentMode  # noqa: E402
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner  # noqa: E402
from regimeshift.orchestration.pipeline import DecisionPipeline  # noqa: E402
from regimeshift.services.alpaca_cli import AlpacaCliAdapter  # noqa: E402
from regimeshift.services.market_data import AlpacaMarketDataProvider  # noqa: E402


def run_cycle(
    settings: Settings,
    *,
    execute: bool,
    limit: int,
    target_dte: int,
    submitted_signals: set[str],
) -> dict[str, object]:
    market_data = AlpacaMarketDataProvider(settings)
    histories = market_data.get_price_history(["SPY", *LARGE_CAP_UNIVERSE], days=365)
    scan = LargeCapScanner().scan(
        histories,
        limit=limit,
        source="Alpaca IEX fully adjusted daily bars",
    )
    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_only": True,
        "scan": scan.model_dump(mode="json"),
        "execution": {"status": "no_trade", "reason": "No actionable setup"},
    }
    candidate = next((item for item in scan.candidates if item.actionable), None)
    if candidate is None:
        return summary
    signal_key = f"{candidate.symbol}:{candidate.as_of.date()}:{candidate.pattern.value}"
    if execute and signal_key in submitted_signals:
        summary["execution"] = {
            "status": "duplicate_blocked",
            "reason": "This symbol, bar, and pattern were already submitted",
        }
        return summary

    snapshot = DecisionPipeline(settings, market_data).analyze(
        candidate.symbol,
        AnalysisControls(
            instrument_mode=InstrumentMode.EQUITY_OPTION,
            min_confidence=max(0.55, candidate.conviction),
            target_dte=target_dte,
        ),
    )
    summary["decision"] = {
        "decision_id": snapshot.decision_id,
        "symbol": candidate.symbol,
        "scanner_conviction": candidate.conviction,
        "council_approved": snapshot.council.approved,
        "risk_approved": snapshot.risk.approved,
        "strategy": snapshot.strategy.display_name,
    }
    if not snapshot.council.approved or not snapshot.risk.approved:
        summary["execution"] = {
            "status": "no_trade",
            "reason": "Council or deterministic Risk Agent rejected the setup",
        }
        return summary

    cli = AlpacaCliAdapter(settings)
    verification = cli.verify()
    if execute and not bool(verification["clock"].get("is_open")):
        summary["cli"] = verification
        summary["execution"] = {
            "status": "market_closed",
            "reason": "Paper submission waits for an open market",
        }
        return summary

    plan = cli.prepare_spread(snapshot)
    result = cli.submit_or_preview(snapshot, plan, execute=execute)
    if result["status"] == "submitted":
        submitted_signals.add(signal_key)
        STATE_PATH.write_text(
            json.dumps({"submitted_signals": sorted(submitted_signals)}, indent=2) + "\n",
            encoding="utf-8",
        )
    summary["cli"] = verification
    summary["plan"] = {key: value for key, value in plan.items() if key != "legs"}
    summary["execution"] = {
        "status": result["status"],
        "allowed": result["allowed"],
        "paper_only": result["paper_only"],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--target-dte", type=int, default=30)
    args = parser.parse_args()
    if not 5 <= args.interval_minutes <= 240:
        parser.error("--interval-minutes must be between 5 and 240")
    if not 1 <= args.limit <= len(LARGE_CAP_UNIVERSE):
        parser.error(f"--limit must be between 1 and {len(LARGE_CAP_UNIVERSE)}")

    settings = Settings(market_data_mode="alpaca", alpaca_cli_enabled=True)
    submitted_signals: set[str] = set()
    if STATE_PATH.is_file():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            submitted_signals = set(state.get("submitted_signals", []))
        except (json.JSONDecodeError, OSError, AttributeError):
            if args.execute:
                print("Scanner state is unreadable; refusing paper execution.", file=sys.stderr)
                return 1
    while True:
        try:
            report = run_cycle(
                settings,
                execute=args.execute,
                limit=args.limit,
                target_dte=args.target_dte,
                submitted_signals=submitted_signals,
            )
            print(json.dumps(report, indent=2, default=str), flush=True)
        except Exception as error:  # keep an explicitly requested loop observable
            print(
                json.dumps(
                    {
                        "generated_at": datetime.now(UTC).isoformat(),
                        "paper_only": True,
                        "error": str(error)[:500],
                    },
                    indent=2,
                ),
                flush=True,
            )
            if not args.loop:
                return 1
        if not args.loop:
            return 0
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None

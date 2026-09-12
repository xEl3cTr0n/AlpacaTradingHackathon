#!/usr/bin/env python3
# ruff: noqa: BLE001, E402
"""Scan liquid large caps and preview/submit the strongest gated paper trade."""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".scanner-state.json"
sys.path.insert(0, str(ROOT / "backend" / "src"))

from gpt_mcp_research import research as gpt_mcp_research
from regimeshift.config import Settings
from regimeshift.domain.backtest_evidence import (
    load_scanner_backtest_evidence,
    scanner_tier_execution_allowed,
)
from regimeshift.domain.models import (
    AgentVerdict,
    AnalysisControls,
    InstrumentMode,
    Stance,
)
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner
from regimeshift.orchestration.pipeline import DecisionPipeline
from regimeshift.services.alpaca_cli import AlpacaCliAdapter
from regimeshift.services.market_data import AlpacaMarketDataProvider


def run_managed_exits(cli, *, execute: bool, directions=None, exclude_entries=None):
    """Risk exits run independently of scanner availability and entry eligibility."""
    results, attempted = [], set()
    try:
        assessment = cli.assess_managed_exits(directions)
    except Exception as error:
        return {"results": [], "checks": [], "error": type(error).__name__}, attempted
    for plan in assessment["plans"]:
        if plan["entry_order_id"] in (exclude_entries or set()):
            continue
        attempted.add(plan["entry_order_id"])
        receipt = {
            "underlying_symbol": plan["underlying_symbol"],
            "reasons": plan["reasons"],
            "unrealized_pnl": plan["unrealized_pnl"],
            "paper_only": True,
        }
        try:
            result = cli.submit_exit(plan, execute=execute)
            receipt["status"] = result["status"]
        except ValueError as error:
            receipt.update(status="exit_rejected", rejection_reason=str(error)[:300])
        except Exception as error:
            # An uncertain response must not trigger an immediate duplicate retry.
            receipt.update(
                status="exit_response_unconfirmed", error_type=type(error).__name__
            )
        results.append(receipt)
    return {
        "results": results,
        "checks": assessment["checks"],
        "error": None,
    }, attempted


def run_cycle(
    settings: Settings,
    *,
    execute: bool,
    limit: int,
    target_dte: int,
    submitted_signals: set[str],
    timeframe: str,
    execute_exits: bool | None = None,
) -> dict[str, object]:
    exit_execution = execute if execute_exits is None else execute_exits
    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_only": True,
        "execution": {"status": "no_trade", "reason": "No actionable setup"},
    }
    cli = AlpacaCliAdapter(settings)
    exits, attempted = run_managed_exits(cli, execute=exit_execution)
    summary["managed_exits"] = exits["results"]
    summary["managed_exit_checks"] = exits["checks"]
    if exits["error"]:
        summary["execution"] = {
            "status": "exit_check_failed",
            "error_type": exits["error"],
            "reason": "Managed exposure could not be inspected; new entries paused",
        }
        return summary
    try:
        market_data = AlpacaMarketDataProvider(settings)
        symbols = ["SPY", *LARGE_CAP_UNIVERSE]
        if timeframe == "intraday":
            histories = market_data.get_intraday_history(
                symbols, days=10, bar_minutes=15
            )
            liquidity_histories = market_data.get_price_history(symbols, days=120)
            scan = LargeCapScanner().scan(
                histories,
                limit=limit,
                source="Alpaca IEX fully adjusted 15-minute bars",
                timeframe="15Min",
                liquidity_histories=liquidity_histories,
                annualization_periods=252 * 26,
                evaluation_time=datetime.now(UTC),
            )
        else:
            histories = market_data.get_price_history(symbols, days=365)
            scan = LargeCapScanner().scan(
                histories,
                limit=limit,
                source="Alpaca IEX fully adjusted daily bars",
                timeframe="1Day",
            )
    except Exception as error:
        summary["execution"] = {
            "status": "scanner_unavailable",
            "error_type": type(error).__name__,
            "reason": "Scanner failed after independent managed-exit checks; no new entry",
        }
        return summary
    execution_gates = load_scanner_backtest_evidence(ROOT).model_copy(
        update={
            "paper_experiment_enabled": settings.paper_experiment_mode
            and settings.alpaca_paper
        }
    )
    scan = scan.model_copy(update={"execution_gates": execution_gates})
    summary["scan"] = scan.model_dump(mode="json")
    directions = {
        candidate.symbol: candidate.direction
        for candidate in scan.candidates
        if candidate.diagnostics is not None and not candidate.diagnostics.stale
    }
    if directions:
        reversal_exits, _ = run_managed_exits(
            cli,
            execute=exit_execution,
            directions=directions,
            exclude_entries=attempted,
        )
        summary["managed_exits"].extend(reversal_exits["results"])
        summary["managed_exit_checks"].extend(reversal_exits["checks"])
        if reversal_exits["error"]:
            summary["execution"] = {
                "status": "exit_check_failed",
                "error_type": reversal_exits["error"],
                "reason": "Post-scan exit inspection failed; new entries paused",
            }
            return summary
    try:
        return run_entry_phase(
            settings,
            cli=cli,
            market_data=market_data,
            scan=scan,
            execution_gates=execution_gates,
            summary=summary,
            execute=execute,
            target_dte=target_dte,
            submitted_signals=submitted_signals,
        )
    except Exception as error:
        # Keep completed exit receipts even if later research, broker I/O, or
        # local entry-state persistence fails. Never retry an uncertain submit here.
        summary["execution"] = {
            "status": "entry_phase_failed",
            "error_type": type(error).__name__,
            "reason": "Entry phase failed; reconcile broker before retrying "
            "any attempted submission",
        }
        return summary


def run_entry_phase(
    settings,
    *,
    cli,
    market_data,
    scan,
    execution_gates,
    summary,
    execute,
    target_dte,
    submitted_signals,
):
    verification: dict[str, object] | None = None
    candidates = [item for item in scan.candidates if item.actionable]
    if not candidates:
        return summary
    summary["evaluations"] = []
    pipeline = DecisionPipeline(settings, market_data)
    for candidate in candidates:
        signal_key = f"{candidate.symbol}:{candidate.as_of.isoformat()}:{candidate.pattern.value}"
        exploration = candidate.signal_tier == "exploration"
        research_advice = None
        if settings.enable_gpt_mcp_research:
            try:
                advice = asyncio.run(gpt_mcp_research(candidate.symbol))
                research_advice = AgentVerdict(
                    agent="GPT Research",
                    stance=Stance(advice.stance),
                    confidence=advice.confidence,
                    summary=advice.thesis,
                    evidence=[*advice.evidence, *advice.risks],
                )
            except Exception as error:
                summary.setdefault("advisory_errors", []).append(
                    {
                        "symbol": candidate.symbol,
                        "provider": "OpenAI GPT + Alpaca MCP",
                        "error": str(error)[:300],
                    }
                )
        snapshot = pipeline.analyze(
            candidate.symbol,
            AnalysisControls(
                instrument_mode=InstrumentMode.EQUITY_OPTION,
                min_confidence=max(0.55, candidate.conviction),
                target_dte=target_dte,
                max_loss_cap_dollars=(
                    candidate.risk_cap_dollars if exploration else None
                ),
            ),
            scanner_signal=candidate,
            research_advice=research_advice,
        )
        evaluation = {
            "decision_id": snapshot.decision_id,
            "symbol": candidate.symbol,
            "signal_tier": candidate.signal_tier,
            "scanner_conviction": candidate.conviction,
            "council_approved": snapshot.council.approved,
            "council_support": snapshot.council.support_count,
            "risk_approved": snapshot.risk.approved,
            "risk_cap_dollars": snapshot.risk.max_allowed_loss,
            "strategy": snapshot.strategy.display_name,
        }
        tier_allowed, tier_reason = scanner_tier_execution_allowed(
            execution_gates,
            timeframe=scan.timeframe,
            signal_tier=candidate.signal_tier,
            exploration_enabled=settings.enable_exploration_orders,
        )
        evaluation["entry_policy_open"] = tier_allowed
        evaluation["entry_policy_reason"] = tier_reason
        evaluation["paper_experiment"] = execution_gates.paper_experiment_enabled
        summary["evaluations"].append(evaluation)
        if not snapshot.council.approved or not snapshot.risk.approved:
            continue

        client_order_id = cli.signal_client_order_id(signal_key)
        if execute and (
            signal_key in submitted_signals
            or cli.existing_order(client_order_id) is not None
        ):
            evaluation["result"] = "duplicate_blocked"
            continue
        verification = verification or cli.verify()
        candidate_execute = execute and tier_allowed
        if execute and not candidate_execute:
            evaluation["result"] = "tier_gate_closed"
            evaluation["reason"] = tier_reason
            continue
        if candidate_execute and not bool(verification["clock"].get("is_open")):
            summary["cli"] = verification
            summary["execution"] = {
                "status": "market_closed",
                "reason": "Paper submission waits for an open market",
            }
            return summary
        try:
            plan = cli.prepare_spread(snapshot)
            result = cli.submit_or_preview(
                snapshot,
                plan,
                execute=candidate_execute,
                client_order_id=client_order_id,
            )
        except ValueError as error:
            evaluation["result"] = "contract_gate_rejected"
            evaluation["reason"] = str(error)[:300]
            continue
        if result["status"] == "submitted":
            submitted_signals.add(signal_key)
            STATE_PATH.write_text(
                json.dumps({"submitted_signals": sorted(submitted_signals)}, indent=2)
                + "\n",
                encoding="utf-8",
            )
        summary["decision"] = evaluation
        summary["cli"] = verification
        summary["plan"] = {key: value for key, value in plan.items() if key != "legs"}
        summary["execution"] = {
            "status": result["status"],
            "allowed": result["allowed"],
            "paper_only": result["paper_only"],
            "signal_tier": candidate.signal_tier,
            "exploration_execution_enabled": settings.enable_exploration_orders,
        }
        return summary
    summary["execution"] = {
        "status": "no_trade",
        "reason": "Every scanner candidate was rejected by council, risk, or contract gates",
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--execute-exits",
        action="store_true",
        help="Execute eligible managed paper exits even when new entries are preview-only",
    )
    parser.add_argument("--loop", action="store_true")
    parser.add_argument(
        "--market-session",
        action="store_true",
        help="Wait before today's open and stop when the next open is another date",
    )
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--target-dte", type=int, default=30)
    parser.add_argument(
        "--timeframe", choices=("intraday", "daily"), default="intraday"
    )
    args = parser.parse_args()
    if not 5 <= args.interval_minutes <= 240:
        parser.error("--interval-minutes must be between 5 and 240")
    if not 1 <= args.limit <= len(LARGE_CAP_UNIVERSE):
        parser.error(f"--limit must be between 1 and {len(LARGE_CAP_UNIVERSE)}")
    if args.max_cycles < 0:
        parser.error("--max-cycles cannot be negative")

    settings = Settings(market_data_mode="alpaca", alpaca_cli_enabled=True)
    entry_execution = args.execute
    submitted_signals: set[str] = set()
    if STATE_PATH.is_file():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            submitted_signals = set(state.get("submitted_signals", []))
        except (json.JSONDecodeError, OSError, AttributeError):
            if args.execute:
                print(
                    "Scanner state is unreadable; new entries disabled, "
                    "managed exits remain eligible.",
                    file=sys.stderr,
                )
                entry_execution = False
    completed_cycles = 0
    while True:
        if args.market_session:
            try:
                verification = AlpacaCliAdapter(settings).verify()
            except Exception as error:
                print(
                    json.dumps(
                        {
                            "generated_at": datetime.now(UTC).isoformat(),
                            "paper_only": True,
                            "error": f"Paper clock check failed: {str(error)[:400]}",
                        },
                        indent=2,
                    ),
                    flush=True,
                )
                if not args.loop:
                    return 1
                time.sleep(args.interval_minutes * 60)
                continue
            clock = verification["clock"]
            if not bool(clock.get("is_open")):
                timestamp = datetime.fromisoformat(str(clock["timestamp"]))
                next_open = datetime.fromisoformat(str(clock["next_open"]))
                if timestamp.date() != next_open.date():
                    print(
                        json.dumps(
                            {
                                "generated_at": datetime.now(UTC).isoformat(),
                                "paper_only": True,
                                "execution": {
                                    "status": "market_closed",
                                    "reason": "Next paper session opens on another date; "
                                    "worker stopped",
                                },
                            },
                            indent=2,
                        ),
                        flush=True,
                    )
                    return 0
                print(
                    json.dumps(
                        {
                            "generated_at": datetime.now(UTC).isoformat(),
                            "paper_only": True,
                            "execution": {
                                "status": "waiting_for_open",
                                "next_open": clock["next_open"],
                            },
                        },
                        indent=2,
                    ),
                    flush=True,
                )
                time.sleep(args.interval_minutes * 60)
                continue
        try:
            report = run_cycle(
                settings,
                execute=entry_execution,
                execute_exits=args.execute or args.execute_exits,
                limit=args.limit,
                target_dte=args.target_dte,
                submitted_signals=submitted_signals,
                timeframe=args.timeframe,
            )
            print(json.dumps(report, indent=2, default=str), flush=True)
            completed_cycles += 1
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
        if args.max_cycles and completed_cycles >= args.max_cycles:
            return 0
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None

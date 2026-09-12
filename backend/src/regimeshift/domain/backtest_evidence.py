import json
from datetime import datetime
from pathlib import Path

from regimeshift.domain.frozen_backtest_evidence import (
    DAILY_SCANNER_REPORT,
    INTRADAY_SCANNER_REPORT,
)
from regimeshift.domain.models import ScannerExecutionGates
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner
from regimeshift.domain.scanner_backtest import IntradayScannerBacktester


def validate_scanner_backtest_evidence(
    intraday_report: dict[str, object],
    daily_report: dict[str, object],
    *,
    source: str = "committed backtest reports",
) -> ScannerExecutionGates:
    """Bind displayed and executable tier state to the same frozen evidence."""
    if not isinstance(intraday_report, dict) or not isinstance(daily_report, dict):
        raise ValueError("Backtest reports must be structured objects")
    scanner = LargeCapScanner()
    expected_intraday = {
        "ema_period": scanner.ema_period,
        "trend_ema_period": scanner.trend_period,
        "timeframe": "15Min",
        "production_conviction": scanner.minimum_conviction,
        "exploration_conviction": scanner.exploration_conviction,
        "friction": IntradayScannerBacktester.friction,
    }
    intraday_parameters = intraday_report.get("parameters", {})
    daily_parameters = daily_report.get("parameters", {})
    if not isinstance(intraday_parameters, dict) or not isinstance(daily_parameters, dict):
        raise ValueError("Backtest parameters must be structured objects")

    problems = [
        f"intraday {key}: expected {value}, report has {intraday_parameters.get(key)}"
        for key, value in expected_intraday.items()
        if intraday_parameters.get(key) != value
    ]
    for label, report, fields in (
        ("intraday", intraday_report, ("production_gate_passed", "exploration_gate_passed")),
        ("daily", daily_report, ("production_gate_passed",)),
    ):
        for field in fields:
            if not isinstance(report.get(field), bool):
                problems.append(f"{label} {field}: requires an explicit boolean")
    if intraday_report.get("universe_size") != len(LARGE_CAP_UNIVERSE):
        problems.append("scanner universe changed after the intraday backtest")
    for key, value in {
        "ema_period": scanner.ema_period,
        "trend_ema_period": scanner.trend_period,
        "minimum_conviction": scanner.minimum_conviction,
        "minimum_average_dollar_volume": scanner.minimum_average_dollar_volume,
    }.items():
        if daily_parameters.get(key) != value:
            problems.append(
                f"daily {key}: expected {value}, report has {daily_parameters.get(key)}"
            )

    evidence_valid = not problems
    timestamps = []
    for report in (intraday_report, daily_report):
        raw_timestamp = report.get("generated_at")
        if isinstance(raw_timestamp, str):
            timestamps.append(datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")))
    evidence_as_of = max(timestamps) if timestamps else None
    production = evidence_valid and intraday_report.get("production_gate_passed") is True
    exploration = evidence_valid and intraday_report.get("exploration_gate_passed") is True
    daily_production = evidence_valid and daily_report.get("production_gate_passed") is True
    details = problems or [
        f"Intraday production holdout: {'passed' if production else 'locked'}",
        f"Intraday exploration holdout: {'passed' if exploration else 'locked'}",
        f"Daily production holdout: {'passed' if daily_production else 'locked'}",
        "Runtime switches, market clock, council, liquidity, and Risk Agent still apply",
    ]
    return ScannerExecutionGates(
        evidence_valid=evidence_valid,
        evidence_as_of=evidence_as_of,
        source=source,
        intraday_production_backtest_passed=production,
        intraday_exploration_backtest_passed=exploration,
        daily_production_backtest_passed=daily_production,
        details=details,
    )


def load_scanner_backtest_evidence(root: Path | None = None) -> ScannerExecutionGates:
    try:
        if root is None:
            intraday_report = INTRADAY_SCANNER_REPORT
            daily_report = DAILY_SCANNER_REPORT
            source = "Packaged Alpaca chronological backtest reports"
        else:
            intraday_text = (root / "docs" / "intraday-scanner-backtest-results.json").read_text(
                encoding="utf-8"
            )
            daily_text = (root / "docs" / "scanner-backtest-results.json").read_text(
                encoding="utf-8"
            )
            intraday_report = json.loads(intraday_text)
            daily_report = json.loads(daily_text)
            source = "Committed Alpaca chronological backtest reports"
        return validate_scanner_backtest_evidence(
            intraday_report,
            daily_report,
            source=source,
        )
    except (OSError, ValueError, TypeError) as error:
        return ScannerExecutionGates(
            evidence_valid=False,
            source="Backtest evidence unavailable",
            intraday_production_backtest_passed=False,
            intraday_exploration_backtest_passed=False,
            daily_production_backtest_passed=False,
            details=[f"Fail closed: {type(error).__name__}"],
        )


def scanner_tier_execution_allowed(
    gates: ScannerExecutionGates,
    *,
    timeframe: str,
    signal_tier: str,
    exploration_enabled: bool,
) -> tuple[bool, str]:
    """Separate experimental paper authorization from claims about backtests."""
    if not gates.paper_only:
        return False, "Scanner execution is paper-only"
    if signal_tier == "watch":
        return False, "Watch signals are never execution eligible"
    supported = (timeframe, signal_tier) in {
        ("1Day", "production"),
        ("15Min", "production"),
        ("15Min", "exploration"),
    }
    if not supported:
        return False, f"Unsupported scanner timeframe or tier: {timeframe}/{signal_tier}"
    if signal_tier == "exploration" and not exploration_enabled:
        return False, "Intraday exploration runtime switch is closed"
    if gates.paper_experiment_enabled:
        return True, (
            "Paper experiment authorized; holdout not required or claimed passed. "
            "Council, risk, liquidity, account, and market-clock gates still apply"
        )
    if not gates.evidence_valid:
        return False, "Backtest evidence is invalid or unavailable"
    if timeframe == "1Day":
        if signal_tier != "production":
            return False, "Daily exploration has no validated execution policy"
        if not gates.daily_production_backtest_passed:
            return False, "Daily production holdout gate is locked"
        return True, "Daily production holdout gate passed"
    if timeframe == "15Min":
        if signal_tier == "production":
            if not gates.intraday_production_backtest_passed:
                return False, "Intraday production holdout gate is locked"
            return True, "Intraday production holdout gate passed"
        if signal_tier == "exploration":
            if not gates.intraday_exploration_backtest_passed:
                return False, "Intraday exploration holdout gate is locked"
            if not exploration_enabled:
                return False, "Intraday exploration runtime switch is closed"
            return True, "Intraday exploration holdout and runtime gates passed"
    return False, f"Unsupported scanner timeframe or tier: {timeframe}/{signal_tier}"

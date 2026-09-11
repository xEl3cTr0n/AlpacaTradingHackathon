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
    production = evidence_valid and bool(intraday_report.get("production_gate_passed"))
    exploration = evidence_valid and bool(intraday_report.get("exploration_gate_passed"))
    daily_production = evidence_valid and bool(daily_report.get("production_gate_passed"))
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
    except (OSError, ValueError, json.JSONDecodeError) as error:
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
    """Resolve one scanner tier against frozen evidence and runtime switches."""
    if not gates.evidence_valid:
        return False, "Backtest evidence is invalid or unavailable"
    if signal_tier == "watch":
        return False, "Watch signals are never execution eligible"
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

#!/usr/bin/env python3
"""Fail closed when committed production evidence does not match scanner policy."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner  # noqa: E402
from regimeshift.domain.scanner_backtest import IntradayScannerBacktester  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    report = json.loads(
        (ROOT / "docs" / "intraday-scanner-backtest-results.json").read_text(
            encoding="utf-8"
        )
    )
    daily_report = json.loads(
        (ROOT / "docs" / "scanner-backtest-results.json").read_text(encoding="utf-8")
    )
    scanner = LargeCapScanner()
    expected = {
        "ema_period": scanner.ema_period,
        "trend_ema_period": scanner.trend_period,
        "timeframe": "15Min",
        "production_conviction": scanner.minimum_conviction,
        "exploration_conviction": scanner.exploration_conviction,
        "friction": IntradayScannerBacktester.friction,
    }
    actual = report.get("parameters", {})
    problems = [
        f"{key}: expected {value}, report has {actual.get(key)}"
        for key, value in expected.items()
        if actual.get(key) != value
    ]
    if report.get("universe_size") != len(LARGE_CAP_UNIVERSE):
        problems.append("scanner universe changed after the committed backtest")
    daily_parameters = daily_report.get("parameters", {})
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
    if problems:
        print("Backtest gate closed: " + "; ".join(problems), file=sys.stderr)
        return 2
    production = bool(report.get("production_gate_passed"))
    exploration = bool(report.get("exploration_gate_passed"))
    daily_production = bool(daily_report.get("production_gate_passed"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"production_gate={'true' if production else 'false'}\n")
            output.write(f"exploration_gate={'true' if exploration else 'false'}\n")
            output.write(
                f"daily_production_gate={'true' if daily_production else 'false'}\n"
            )
    print(
        "Intraday backtest evidence valid. "
        f"Intraday production: {production}. Intraday exploration: {exploration}. "
        f"Daily production: {daily_production}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed when committed production evidence does not match scanner policy."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.domain.backtest_evidence import load_scanner_backtest_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    gates = load_scanner_backtest_evidence(ROOT)
    if not gates.evidence_valid:
        print("Backtest gate closed: " + "; ".join(gates.details), file=sys.stderr)
        return 2
    production = gates.intraday_production_backtest_passed
    exploration = gates.intraday_exploration_backtest_passed
    daily_production = gates.daily_production_backtest_passed
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

"""Gate-critical projection of the committed Alpaca backtest reports.

Keep this small Python projection deployable with serverless source tracing. The
repository verifier still reads the full JSON reports and tests ensure both
projections produce the same execution-gate state.
"""

INTRADAY_SCANNER_REPORT: dict[str, object] = {
    "generated_at": "2026-09-05T11:29:33.473594+00:00",
    "parameters": {
        "timeframe": "15Min",
        "ema_period": 18,
        "trend_ema_period": 50,
        "production_conviction": 0.6,
        "exploration_conviction": 0.55,
        "holding_bars": 8,
        "friction": 0.002,
    },
    "universe_size": 24,
    "production_gate_passed": False,
    "exploration_gate_passed": True,
}

DAILY_SCANNER_REPORT: dict[str, object] = {
    "generated_at": "2026-09-02T10:56:18.191275+00:00",
    "parameters": {
        "ema_period": 18,
        "trend_ema_period": 50,
        "minimum_conviction": 0.6,
        "minimum_average_dollar_volume": 100_000_000,
        "holding_sessions": 3,
    },
    "universe_size": 24,
    "production_gate_passed": True,
}

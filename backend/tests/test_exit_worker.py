import importlib.util
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from regimeshift.config import Settings
from regimeshift.domain.backtest_evidence import load_scanner_backtest_evidence


@pytest.fixture
def runner(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "scanner_runner_test", scripts / "scanner_runner.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCli:
    def __init__(self):
        self.executions = []
        self.fail_submit = False
        self.plans = [
            {
                "entry_order_id": "test-entry",
                "underlying_symbol": "AAPL",
                "reasons": ["stop"],
                "unrealized_pnl": -80,
            }
        ]

    def assess_managed_exits(self, directions=None):
        return {"plans": self.plans, "checks": [{"status": "exit_ready"}]}

    def submit_exit(self, plan, execute):
        self.executions.append((plan["entry_order_id"], execute))
        if self.fail_submit:
            raise TimeoutError("Ambiguous broker response")
        return {"status": "submitted" if execute else "dry_run"}


@pytest.mark.parametrize(
    "execute_entries,execute_exits,expected_exit",
    [
        (False, True, True),
        (False, False, False),
        (True, None, True),
        (False, None, False),
    ],
)
def test_exits_happen_before_scanner_outage_and_remain_inspectable(
    runner,
    monkeypatch,
    execute_entries,
    execute_exits,
    expected_exit,
):
    cli = FakeCli()
    monkeypatch.setattr(runner, "AlpacaCliAdapter", lambda settings: cli)

    def unavailable(settings):
        assert cli.executions == [("test-entry", expected_exit)]
        raise ConnectionError("Historical bars unavailable")

    monkeypatch.setattr(runner, "AlpacaMarketDataProvider", unavailable)
    report = runner.run_cycle(
        Settings(),
        execute=execute_entries,
        execute_exits=execute_exits,
        limit=1,
        target_dte=30,
        submitted_signals=set(),
        timeframe="intraday",
    )
    assert report["execution"]["status"] == "scanner_unavailable"
    assert len(report["managed_exits"]) == 1
    assert report["managed_exit_checks"][0]["status"] == "exit_ready"
    assert "test-entry" not in str(report)  # private broker identity does not enter public receipt


def test_unknown_exit_response_does_not_retry_or_prevent_other_exits(runner):
    cli = FakeCli()
    cli.plans.append(
        {**cli.plans[0], "entry_order_id": "second-entry", "underlying_symbol": "MSFT"}
    )
    cli.fail_submit = True
    report, attempted = runner.run_managed_exits(cli, execute=True)
    assert len(cli.executions) == 2
    assert attempted == {"test-entry", "second-entry"}
    assert all(r["status"] == "exit_response_unconfirmed" for r in report["results"])
    second, _ = runner.run_managed_exits(cli, execute=True, exclude_entries=attempted)
    assert not second["results"] and len(cli.executions) == 2


def test_invalid_backtest_evidence_cannot_disable_exit_phase(runner, monkeypatch):
    cli = FakeCli()
    monkeypatch.setattr(runner, "AlpacaCliAdapter", lambda settings: cli)
    market = SimpleNamespace(get_price_history=lambda *args, **kwargs: {})
    monkeypatch.setattr(runner, "AlpacaMarketDataProvider", lambda settings: market)
    scan = SimpleNamespace(
        candidates=[],
        model_copy=lambda **kwargs: scan,
        model_dump=lambda **kwargs: {"candidates": []},
    )
    monkeypatch.setattr(
        runner, "LargeCapScanner", lambda: SimpleNamespace(scan=lambda *a, **k: scan)
    )
    monkeypatch.setattr(
        runner,
        "load_scanner_backtest_evidence",
        lambda root: load_scanner_backtest_evidence().model_copy(update={"evidence_valid": False}),
    )
    result = runner.run_cycle(
        Settings(),
        execute=False,
        execute_exits=True,
        limit=1,
        target_dte=30,
        submitted_signals=set(),
        timeframe="daily",
    )
    assert cli.executions == [("test-entry", True)]
    assert result["execution"]["status"] == "no_trade"


def test_unreadable_entry_state_disables_entries_but_keeps_exit_flag(runner, monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    path.write_text("invalid JSON")
    monkeypatch.setattr(runner, "STATE_PATH", path)
    monkeypatch.setattr(sys, "argv", ["scanner_runner.py", "--execute"])
    calls = []

    def fake_cycle(*args, **kwargs):
        calls.append(kwargs)
        return {"paper_only": True}

    monkeypatch.setattr(runner, "run_cycle", fake_cycle)
    assert runner.main() == 0
    assert calls[0]["execute"] is False and calls[0]["execute_exits"] is True


def test_later_entry_exception_does_not_erase_completed_exit_receipts(runner, monkeypatch):
    cli = FakeCli()
    monkeypatch.setattr(runner, "AlpacaCliAdapter", lambda settings: cli)
    monkeypatch.setattr(
        runner,
        "AlpacaMarketDataProvider",
        lambda settings: SimpleNamespace(
            get_price_history=lambda *a, **k: {},
        ),
    )
    scan = SimpleNamespace(
        candidates=[],
        model_copy=lambda **kwargs: scan,
        model_dump=lambda **kwargs: {"candidates": []},
    )
    monkeypatch.setattr(
        runner, "LargeCapScanner", lambda: SimpleNamespace(scan=lambda *a, **k: scan)
    )

    def fail(*args, **kwargs):
        raise ConnectionError("entry broker lookup unavailable")

    monkeypatch.setattr(runner, "run_entry_phase", fail)
    report = runner.run_cycle(
        Settings(),
        execute=False,
        execute_exits=True,
        limit=1,
        target_dte=30,
        submitted_signals=set(),
        timeframe="daily",
    )
    assert report["execution"]["status"] == "entry_phase_failed"
    assert report["managed_exits"][0]["status"] == "submitted"


def test_workflow_keeps_exit_flag_outside_entry_gate_conditions():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/paper-trading.yml"
    ).read_text()
    assert "continue-on-error: true" in workflow
    assert "exit_arguments+=(--execute-exits)" in workflow
    assert '"${daily_arguments[@]}" "${exit_arguments[@]}"' in workflow
    assert '"${intraday_arguments[@]}" "${exit_arguments[@]}"' in workflow


@pytest.mark.parametrize("risk_approved,council_approved", [(False, True), (True, False)])
def test_open_paper_experiment_cannot_override_risk_or_council(
    runner, monkeypatch, risk_approved, council_approved
):
    candidate = SimpleNamespace(
        symbol="AAPL",
        actionable=True,
        as_of=datetime.now(UTC),
        pattern=SimpleNamespace(value="bullish_18ema_cross"),
        signal_tier="production",
        conviction=0.65,
    )
    decision = SimpleNamespace(
        decision_id="test-decision",
        council=SimpleNamespace(approved=council_approved, support_count=5),
        risk=SimpleNamespace(approved=risk_approved, max_allowed_loss=1000),
        strategy=SimpleNamespace(display_name="call debit spread"),
    )
    monkeypatch.setattr(
        runner, "DecisionPipeline", lambda *args: SimpleNamespace(analyze=lambda *a, **k: decision)
    )
    gates = load_scanner_backtest_evidence().model_copy(update={"paper_experiment_enabled": True})
    result = runner.run_entry_phase(
        Settings(
            enable_paper_orders=True, paper_experiment_mode=True, enable_gpt_mcp_research=False
        ),
        cli=SimpleNamespace(),  # Any broker attempt raises: veto must stop beforehand.
        market_data=None,
        scan=SimpleNamespace(candidates=[candidate], timeframe="15Min"),
        execution_gates=gates,
        summary={"execution": {"status": "no_trade"}},
        execute=True,
        target_dte=30,
        submitted_signals=set(),
    )
    assert result["execution"]["status"] == "no_trade"
    evaluation = result["evaluations"][0]
    assert evaluation["entry_policy_open"] and evaluation["paper_experiment"]
    assert evaluation["risk_approved"] is risk_approved
    assert evaluation["council_approved"] is council_approved


@pytest.mark.parametrize("experiment", ["true", "false"])
@pytest.mark.parametrize(
    "paper,gates,exploration",
    [
        ("true", "false", "true"),
        ("true", "true", "true"),
        ("false", "true", "true"),
        ("true", "true", "false"),
    ],
)
def test_actual_workflow_shell_keeps_exit_execution_independent(
    tmp_path, paper, gates, exploration, experiment
):
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/paper-trading.yml"
    ).read_text()
    block = workflow.split("- name: Run gated paper session", 1)[1].split("run: |\n", 1)[1]
    script = textwrap.dedent(block.split("      - name:", 1)[0])
    for field in ("daily_production_gate", "exploration_gate", "production_gate"):
        script = script.replace("${{ steps.backtest.outputs." + field + " }}", gates)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    binary = binary_dir / "python"
    binary.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_WORKER_ARGUMENTS"\n')
    binary.chmod(0o700)
    record = tmp_path / "calls.txt"
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": str(binary_dir) + os.pathsep + os.environ["PATH"],
            "ENABLE_PAPER_ORDERS": paper,
            "ENABLE_EXPLORATION_ORDERS": exploration,
            "PAPER_EXPERIMENT_MODE": experiment,
            "TEST_WORKER_ARGUMENTS": str(record),
        },
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    daily, intraday = [line.split() for line in record.read_text().splitlines()]
    assert ("--execute-exits" in daily) == (paper == "true")
    assert ("--execute-exits" in intraday) == (paper == "true")
    assert ("--execute" in daily) == (paper == "true" and (experiment == "true" or gates == "true"))
    assert ("--execute" in intraday) == (
        paper == "true" and (experiment == "true" or gates == "true")
    )


def test_invalid_evidence_verifier_writes_closed_outputs_even_when_it_fails(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts/verify_backtest_gate.py"
    spec = importlib.util.spec_from_file_location("verify_backtest_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "load_scanner_backtest_evidence",
        lambda root: SimpleNamespace(
            evidence_valid=False,
            intraday_production_backtest_passed=True,
            intraday_exploration_backtest_passed=True,
            daily_production_backtest_passed=True,
            details=["invalid test data"],
        ),
    )
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["verify_backtest_gate.py", "--github-output", str(output)])
    assert module.main() == 2
    assert output.read_text().splitlines() == [
        "production_gate=false",
        "exploration_gate=false",
        "daily_production_gate=false",
    ]

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from regimeshift.config import Settings
from regimeshift.domain.exits import managed_exit_plan
from regimeshift.domain.models import DecisionSnapshot, Direction, StrategyName
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE

ROOT = Path(__file__).resolve().parents[4]


class AlpacaCliAdapter:
    """Constrained Alpaca CLI adapter that can never route to live trading."""

    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca paper credentials are not configured")
        workspace_binary = ROOT / ".alpaca-cli" / "alpaca"
        system_binary = shutil.which("alpaca")
        if workspace_binary.is_file():
            self.binary = str(workspace_binary)
        elif system_binary:
            self.binary = system_binary
        else:
            raise ValueError(
                "Alpaca CLI is not installed; run the documented local installer first"
            )
        self.settings = settings

    def verify(self) -> dict[str, object]:
        account = self._run(
            [
                "account",
                "get",
                "--quiet",
                "--jq",
                "{status: .status, options_buying_power_available: "
                "(.options_buying_power != null)}",
            ]
        )
        clock = self._run(
            [
                "clock",
                "--quiet",
                "--jq",
                "{timestamp: .timestamp, is_open: .is_open}",
            ]
        )
        return {"account": account, "clock": clock, "paper_only": True}

    def prepare_index_spread(self, snapshot: DecisionSnapshot) -> dict[str, Any]:
        if snapshot.strategy.underlying_symbol != "XSP":
            raise ValueError("Index-spread execution is restricted to validated XSP signals")
        return self.prepare_spread(snapshot)

    def prepare_spread(self, snapshot: DecisionSnapshot) -> dict[str, Any]:
        underlying = snapshot.strategy.underlying_symbol
        if underlying not in {"XSP", *LARGE_CAP_UNIVERSE}:
            raise ValueError("CLI execution is restricted to the scanner universe or XSP")
        if snapshot.strategy.name not in {
            StrategyName.BULL_CALL_SPREAD,
            StrategyName.BEAR_PUT_SPREAD,
        }:
            raise ValueError("Only defined-risk directional debit spreads are executable")

        target = snapshot.controls.target_dte
        today = datetime.now(UTC).date()
        start = today + timedelta(days=max(21 if underlying == "XSP" else 7, target - 5))
        end = today + timedelta(days=min(45 if underlying == "XSP" else 60, target + 5))
        option_type = (
            "call"
            if snapshot.strategy.name == StrategyName.BULL_CALL_SPREAD
            else "put"
        )
        spot = snapshot.market.current_price
        contracts_payload = self._run(
            [
                "option",
                "contracts",
                "--underlying-symbols",
                underlying,
                "--style",
                "european" if underlying == "XSP" else "american",
                "--status",
                "active",
                "--expiration-date-gte",
                start.isoformat(),
                "--expiration-date-lte",
                end.isoformat(),
                "--strike-price-gte",
                f"{spot * 0.92:.2f}",
                "--strike-price-lte",
                f"{spot * 1.08:.2f}",
                "--type",
                option_type,
                "--limit",
                "1000",
                "--quiet",
            ]
        )
        contracts = [
            contract
            for contract in contracts_payload.get("option_contracts", [])
            if contract.get("tradable")
        ]
        if len(contracts) < 2:
            raise ValueError(f"Alpaca CLI returned too few tradable {underlying} contracts")

        expiry = min(
            {contract["expiration_date"] for contract in contracts},
            key=lambda value: abs(
                (datetime.fromisoformat(value).date() - today).days - target
            ),
        )
        same_expiry = [contract for contract in contracts if contract["expiration_date"] == expiry]
        long_contract = min(
            same_expiry,
            key=lambda contract: abs(float(contract["strike_price"]) - spot),
        )
        long_strike = float(long_contract["strike_price"])
        short_candidates = [
            contract
            for contract in same_expiry
            if (
                float(contract["strike_price"]) > long_strike
                if option_type == "call"
                else float(contract["strike_price"]) < long_strike
            )
        ]
        if not short_candidates:
            raise ValueError(f"No protective short leg was available for {underlying}")
        target_width = max(1.0, spot * 0.02)
        target_short_strike = long_strike + (
            target_width if option_type == "call" else -target_width
        )
        short_contract = min(
            short_candidates,
            key=lambda contract: abs(
                float(contract["strike_price"]) - target_short_strike
            ),
        )
        short_strike = float(short_contract["strike_price"])
        chain = self._run(
            [
                "data",
                "option",
                "chain",
                "--underlying-symbol",
                underlying,
                "--expiration-date",
                expiry,
                "--strike-price-gte",
                f"{min(long_strike, short_strike):.2f}",
                "--strike-price-lte",
                f"{max(long_strike, short_strike):.2f}",
                "--type",
                option_type,
                "--limit",
                "100",
                "--quiet",
            ]
        )
        snapshots = chain.get("snapshots", {})
        long_quote = self._quote(snapshots, long_contract["symbol"])
        short_quote = self._quote(snapshots, short_contract["symbol"])
        debit = round(max(0.01, long_quote["ask"] - short_quote["bid"]), 2)
        maximum_loss = round(debit * 100, 2)
        width = abs(short_strike - long_strike)
        maximum_reward = round(max(0.0, width * 100 - maximum_loss), 2)
        long_open_interest = self._open_interest(long_contract)
        short_open_interest = self._open_interest(short_contract)
        open_interest_passed = underlying == "XSP" or (
            long_open_interest is not None
            and short_open_interest is not None
            and min(long_open_interest, short_open_interest) >= 50
        )
        liquid = (
            self._liquid(long_quote)
            and self._liquid(short_quote)
            and open_interest_passed
        )

        return {
            "provider": "Alpaca CLI 0.0.14",
            "paper_only": True,
            "order_class": "mleg",
            "underlying_symbol": underlying,
            "signal_symbol": snapshot.market.symbol,
            "expiration": expiry,
            "option_type": option_type,
            "quantity": 1,
            "limit_debit": debit,
            "maximum_loss": maximum_loss,
            "maximum_reward": maximum_reward,
            "liquidity_passed": liquid,
            "open_interest_floor": 50 if underlying != "XSP" else None,
            "long_open_interest": long_open_interest,
            "short_open_interest": short_open_interest,
            "legs": [
                {
                    "symbol": long_contract["symbol"],
                    "ratio_qty": "1",
                    "side": "buy",
                    "position_intent": "buy_to_open",
                },
                {
                    "symbol": short_contract["symbol"],
                    "ratio_qty": "1",
                    "side": "sell",
                    "position_intent": "sell_to_open",
                },
            ],
        }

    def submit_or_preview(
        self,
        snapshot: DecisionSnapshot,
        plan: dict[str, Any],
        execute: bool,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        allowed = (
            snapshot.risk.approved
            and snapshot.council.approved
            and plan["paper_only"]
            and plan["liquidity_passed"]
            and plan["maximum_loss"] <= snapshot.risk.max_allowed_loss
        )
        if execute and not self.settings.enable_paper_orders:
            raise ValueError("ENABLE_PAPER_ORDERS must be true for CLI submission")
        if execute and not allowed:
            raise ValueError("Deterministic execution gates rejected the order")

        arguments = [
            "order",
            "submit",
            "--order-class",
            "mleg",
            "--qty",
            str(plan["quantity"]),
            "--type",
            "limit",
            "--limit-price",
            f"{plan['limit_debit']:.2f}",
            "--time-in-force",
            "day",
            "--client-order-id",
            client_order_id or f"regimeshift-{snapshot.decision_id}",
            "--legs",
            json.dumps(plan["legs"], separators=(",", ":")),
            "--quiet",
        ]
        if not execute:
            arguments.insert(2, "--dry-run")
        result = self._run(arguments)
        return {
            "status": "submitted" if execute else "dry_run",
            "allowed": allowed,
            "paper_only": True,
            "order": result,
        }

    @staticmethod
    def signal_client_order_id(signal_key: str) -> str:
        """Return a stable, Alpaca-safe ID for one symbol/date/pattern signal."""
        digest = hashlib.sha256(signal_key.encode("utf-8")).hexdigest()[:24]
        return f"regimeshift-signal-{digest}"

    def existing_order(self, client_order_id: str) -> dict[str, str] | None:
        """Check Alpaca itself so duplicate protection survives ephemeral runners."""
        from alpaca.common.exceptions import APIError
        from alpaca.trading.client import TradingClient

        client = TradingClient(
            self.settings.alpaca_api_key,
            self.settings.alpaca_secret_key.get_secret_value(),
            paper=True,
        )
        try:
            order = client.get_order_by_client_id(client_order_id)
        except APIError as error:
            if error.status_code == 404:
                return None
            raise
        return {
            "id": str(order.id),
            "status": str(getattr(order.status, "value", order.status)),
            "client_order_id": order.client_order_id,
        }

    def managed_exit_plans(
        self, direction_by_symbol: dict[str, Direction] | None = None
    ) -> list[dict[str, Any]]:
        entries = self._run_list(
            ["order", "list", "--status", "closed", "--nested", "--limit", "500", "--quiet"]
        )
        open_orders = self._run_list(
            ["order", "list", "--status", "open", "--nested", "--limit", "500", "--quiet"]
        )
        positions = {
            item["symbol"]: item
            for item in self._run_list(["position", "list", "--quiet"])
            if item.get("asset_class") in {"us_option", "us_index"}
        }
        open_client_ids = {str(item.get("client_order_id", "")) for item in open_orders}
        plans: list[dict[str, Any]] = []
        for entry in entries:
            exit_client_id = f"regimeshift-exit-{str(entry.get('id', ''))[:32]}"
            if exit_client_id in open_client_ids:
                continue
            underlying = ""
            legs = entry.get("legs") or []
            if legs:
                symbol = str(legs[0].get("symbol", ""))
                underlying = symbol[:-15].rstrip()
            plan = managed_exit_plan(
                entry,
                positions,
                current_direction=(direction_by_symbol or {}).get(underlying),
            )
            if plan is not None:
                plan["client_order_id"] = exit_client_id
                plans.append(plan)
        return plans

    def submit_exit(self, plan: dict[str, Any], *, execute: bool) -> dict[str, Any]:
        if not plan.get("paper_only") or len(plan.get("legs", [])) != 2:
            raise ValueError("Managed exits require a complete paper-only two-leg spread")
        if execute and not self.settings.enable_paper_orders:
            raise ValueError("ENABLE_PAPER_ORDERS must be true for CLI submission")
        arguments = [
            "order",
            "submit",
            "--order-class",
            "mleg",
            "--qty",
            str(plan["quantity"]),
            "--type",
            "market",
            "--time-in-force",
            "day",
            "--client-order-id",
            plan["client_order_id"],
            "--legs",
            json.dumps(plan["legs"], separators=(",", ":")),
            "--quiet",
        ]
        if not execute:
            arguments.insert(2, "--dry-run")
        order = self._run(arguments)
        return {
            "status": "submitted" if execute else "dry_run",
            "paper_only": True,
            "order": order,
        }

    @staticmethod
    def _quote(snapshots: dict[str, Any], symbol: str) -> dict[str, float]:
        quote = snapshots.get(symbol, {}).get("latestQuote", {})
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
        bid_size = float(quote.get("bs") or 0)
        ask_size = float(quote.get("as") or 0)
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError(f"Invalid option quote returned for {symbol}")
        return {"bid": bid, "ask": ask, "bid_size": bid_size, "ask_size": ask_size}

    @staticmethod
    def _liquid(quote: dict[str, float]) -> bool:
        midpoint = (quote["bid"] + quote["ask"]) / 2
        return (
            quote["bid_size"] > 0
            and quote["ask_size"] > 0
            and (quote["ask"] - quote["bid"]) / midpoint <= 0.2
        )

    @staticmethod
    def _open_interest(contract: dict[str, Any]) -> int | None:
        value = contract.get("open_interest")
        if value in {None, ""}:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _run(self, arguments: list[str]) -> dict[str, Any]:
        payload = self._run_payload(arguments)
        if not isinstance(payload, dict):
            raise ValueError("Alpaca CLI returned an unexpected response shape")
        return payload

    def _run_list(self, arguments: list[str]) -> list[dict[str, Any]]:
        payload = self._run_payload(arguments)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise ValueError("Alpaca CLI returned an unexpected list response")
        return payload

    def _run_payload(self, arguments: list[str]) -> Any:
        environment = os.environ.copy()
        environment.update(
            {
                "ALPACA_API_KEY": self.settings.alpaca_api_key,
                "ALPACA_SECRET_KEY": self.settings.alpaca_secret_key.get_secret_value(),
                "ALPACA_LIVE_TRADE": "false",
                "ALPACA_CONFIG_DIR": str(ROOT / ".alpaca-cli" / "config"),
                "ALPACA_QUIET": "true",
            }
        )
        completed = subprocess.run(
            [self.binary, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
            env=environment,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "Alpaca CLI command failed"
            raise ValueError(detail[:500])
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("Alpaca CLI returned non-JSON output") from error
        return payload

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from regimeshift.config import Settings
from regimeshift.domain.execution_checks import (
    check_option_quote,
    finite_number,
    verify_entry_capacity,
    verify_open_clock,
)
from regimeshift.domain.exits import managed_exit_plan, option_contract_details
from regimeshift.domain.models import DecisionSnapshot, Direction, StrategyName
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE

ROOT = Path(__file__).resolve().parents[4]


class AlpacaCliAdapter:
    """Constrained Alpaca CLI adapter that can never route to live trading."""

    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca paper credentials are not configured")
        if not settings.alpaca_paper:
            raise ValueError("CLI trader refuses non-paper configuration")
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
                "{timestamp: .timestamp, is_open: .is_open, "
                "next_open: .next_open, next_close: .next_close}",
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
        option_type = "call" if snapshot.strategy.name == StrategyName.BULL_CALL_SPREAD else "put"
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
            key=lambda value: abs((datetime.fromisoformat(value).date() - today).days - target),
        )
        same_expiry = [contract for contract in contracts if contract["expiration_date"] == expiry]
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
        snapshots = chain.get("snapshots", {})
        long_contract, short_contract = self.select_spread_contracts(
            same_expiry,
            snapshots,
            spot=spot,
            option_type=option_type,
            risk_cap=min(snapshot.risk.max_allowed_loss, self.settings.max_position_loss_dollars),
            require_open_interest=underlying != "XSP",
        )
        long_strike = float(long_contract["strike_price"])
        short_strike = float(short_contract["strike_price"])
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
        liquid = self._liquid(long_quote) and self._liquid(short_quote) and open_interest_passed

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
            "quote_checks": [long_quote["check"], short_quote["check"]],
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
            reasons = []
            if not snapshot.risk.approved:
                reasons.append("Risk Agent rejected")
            if not snapshot.council.approved:
                reasons.append("council rejected")
            if not plan["paper_only"]:
                reasons.append("paper-only restriction")
            if not plan["liquidity_passed"]:
                reasons.append("quote width, size or open-interest gate failed")
            if plan["maximum_loss"] > snapshot.risk.max_allowed_loss:
                reasons.append("quoted debit exceeds Risk Agent budget")
            raise ValueError("Deterministic execution gates rejected: " + "; ".join(reasons))
        capacity = None
        quote_checks = None
        if execute:
            maximum_loss = self.verify_plan_shape(snapshot, plan)
            capacity = self.verify_execution_capacity(
                plan["underlying_symbol"],
                maximum_loss=maximum_loss,
            )
            verify_open_clock(self._run(["clock", "--quiet"]))
            # Re-fetch after account checks. Never trust prepared-plan quote booleans.
            symbols = [leg["symbol"] for leg in plan["legs"]]
            fresh = self._run(
                [
                    "data",
                    "option",
                    "snapshot",
                    "--symbols",
                    ",".join(symbols),
                    "--quiet",
                ]
            ).get("snapshots", {})
            current = {symbol: self._quote(fresh, symbol) for symbol in symbols}
            long_symbol = next(leg["symbol"] for leg in plan["legs"] if leg["side"] == "buy")
            short_symbol = next(leg["symbol"] for leg in plan["legs"] if leg["side"] == "sell")
            natural = current[long_symbol]["ask"] - current[short_symbol]["bid"]
            width = abs(
                option_contract_details(long_symbol)[3] - option_contract_details(short_symbol)[3]
            )
            if not 0 < natural < width or plan["limit_debit"] > natural * 1.10 + 0.05:
                raise ValueError("Fresh option debit failed the price/width gate; rebuild the plan")
            quote_checks = [current[symbol]["check"] for symbol in symbols]

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
            "execution_capacity": capacity,
            "quote_checks": quote_checks,
        }

    def verify_plan_shape(self, snapshot: DecisionSnapshot, plan: dict[str, Any]) -> float:
        """Recompute submitted debit risk and structure, not caller-provided loss fields."""
        if not self.settings.alpaca_paper or plan.get("paper_only") is not True:
            raise ValueError("CLI submission requires the paper environment")
        if plan.get("quantity") != 1 or isinstance(plan.get("quantity"), bool):
            raise ValueError("CLI debit spreads are restricted to one contract")
        legs = plan.get("legs")
        if not isinstance(legs, list) or len(legs) != 2:
            raise ValueError("CLI submission requires exactly two option legs")
        buys = [
            leg
            for leg in legs
            if leg.get("side") == "buy" and leg.get("position_intent") == "buy_to_open"
        ]
        sells = [
            leg
            for leg in legs
            if leg.get("side") == "sell" and leg.get("position_intent") == "sell_to_open"
        ]
        if (
            len(buys) != 1
            or len(sells) != 1
            or any(finite_number(leg.get("ratio_qty")) != 1 for leg in legs)
        ):
            raise ValueError("CLI submission requires a 1:1 opening debit spread")
        long, short = (option_contract_details(leg["symbol"]) for leg in (buys[0], sells[0]))
        if long[:3] != short[:3] or long[0] != snapshot.strategy.underlying_symbol:
            raise ValueError("Option legs do not match the approved underlying and expiration")
        expected_type = {StrategyName.BULL_CALL_SPREAD: "C", StrategyName.BEAR_PUT_SPREAD: "P"}
        if expected_type.get(snapshot.strategy.name) != long[2]:
            raise ValueError("Option type does not match the approved directional strategy")
        if plan.get("underlying_symbol") != long[0]:
            raise ValueError("Plan underlying does not match its option legs")
        width = (short[3] - long[3]) * (1 if long[2] == "C" else -1)
        debit = finite_number(plan.get("limit_debit"))
        if debit is None or not 0 < debit < width:
            raise ValueError("Submitted debit is invalid relative to spread width")
        loss = round(debit * 100, 2)
        claimed_loss = finite_number(plan.get("maximum_loss"))
        if claimed_loss is None or abs(claimed_loss - loss) > 0.005:
            raise ValueError("Declared maximum loss does not match submitted debit")
        if loss > min(snapshot.risk.max_allowed_loss, self.settings.max_position_loss_dollars):
            raise ValueError("Submitted debit exceeds the deterministic Risk Agent budget")
        dte = (long[1].date() - datetime.now(UTC).date()).days
        if not (21 <= dte <= 45 if long[0] == "XSP" else 7 <= dte <= 60):
            raise ValueError("Submitted expiration is outside the supported DTE range")
        return loss

    def verify_execution_capacity(
        self,
        underlying: str,
        *,
        maximum_loss: float = 0,
    ) -> dict[str, Any]:
        """Fail closed on account loss, exposure, or duplicate-underlying risk."""
        # CLI 0.0.14's typed `account get` output omits false safety flags.
        # Raw GET retains the distinction between verified false and missing.
        account = self._run(
            [
                "api",
                "GET",
                "/v2/account",
                "--quiet",
                "--jq",
                "{equity: .equity, last_equity: .last_equity, status: .status, "
                "trading_blocked: .trading_blocked, account_blocked: .account_blocked, "
                "trade_suspended_by_user: .trade_suspended_by_user, "
                "options_buying_power: .options_buying_power, "
                "options_trading_level: .options_trading_level}",
            ]
        )
        positions = self._run_list(["position", "list", "--quiet"])
        open_orders = self._run_list(
            ["order", "list", "--status", "open", "--nested", "--limit", "500", "--quiet"]
        )
        return verify_entry_capacity(
            self.settings,
            underlying,
            account,
            positions,
            open_orders,
            maximum_loss=maximum_loss,
        )

    @staticmethod
    def signal_client_order_id(signal_key: str) -> str:
        """Return a stable, Alpaca-safe ID for one symbol/date/pattern signal."""
        digest = hashlib.sha256(signal_key.encode("utf-8")).hexdigest()[:24]
        return f"regimeshift-signal-{digest}"

    @staticmethod
    def _option_root(symbol: str) -> str:
        return symbol[:-15].strip() if len(symbol) > 15 else ""

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
                stop_loss_fraction=self.settings.stop_loss_fraction,
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

    @classmethod
    def select_spread_contracts(
        cls,
        contracts: list[dict[str, Any]],
        snapshots: dict[str, Any],
        *,
        spot: float,
        option_type: str,
        risk_cap: float,
        require_open_interest: bool = True,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Prefer near-ATM pairs that satisfy existing quote, OI and debit gates."""
        liquid = []
        for contract in contracts:
            interest = cls._open_interest(contract)
            if require_open_interest and (interest is None or interest < 50):
                continue
            try:
                quote = cls._quote(snapshots, contract["symbol"], now=now)
            except (ValueError, TypeError):
                continue
            if cls._liquid(quote):
                liquid.append((contract, quote))
        if len(liquid) < 2:
            raise ValueError(
                "Fewer than two contracts pass fresh-quote, width, size and open-interest gates"
            )
        liquid.sort(key=lambda item: abs(float(item[0]["strike_price"]) - spot))
        target_width = max(1.0, spot * 0.02)
        pairs = []
        for long_contract, long_quote in liquid[:10]:
            long_strike = float(long_contract["strike_price"])
            for short_contract, short_quote in liquid:
                if long_contract["expiration_date"] != short_contract["expiration_date"]:
                    continue
                short_strike = float(short_contract["strike_price"])
                signed_width = (short_strike - long_strike) * (1 if option_type == "call" else -1)
                if not 0 < signed_width <= target_width * 2:
                    continue
                debit = round(long_quote["ask"] - short_quote["bid"], 2)
                if not 0 < debit < signed_width or round(debit * 100, 2) > risk_cap:
                    continue
                rank = (abs(long_strike - spot), abs(signed_width - target_width), debit)
                pairs.append((rank, long_contract, short_contract))
        if not pairs:
            raise ValueError(
                f"No liquid directional debit spread fits the ${risk_cap:,.0f} Risk Agent budget"
            )
        _, long_contract, short_contract = min(pairs, key=lambda item: item[0])
        return long_contract, short_contract

    @staticmethod
    def _quote(
        snapshots: dict[str, Any],
        symbol: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        quote = snapshots.get(symbol, {}).get("latestQuote", {})
        check = check_option_quote(
            symbol,
            bid=quote.get("bp"),
            ask=quote.get("ap"),
            bid_size=quote.get("bs"),
            ask_size=quote.get("as"),
            timestamp=quote.get("t"),
            now=now,
        )
        if not check.valid:
            raise ValueError(f"Invalid option quote for {symbol}: {'; '.join(check.reasons)}")
        return {
            "bid": check.bid,
            "ask": check.ask,
            "bid_size": float(quote["bs"]),
            "ask_size": float(quote["as"]),
            "check": check.model_dump(mode="json"),
        }

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

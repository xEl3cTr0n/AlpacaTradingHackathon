#!/usr/bin/env python3
"""Check paper-session worker coverage; optionally dispatch a missing worker."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from regimeshift.config import Settings  # noqa: E402

REPOSITORY = "xEl3cTr0n/AlpacaTradingHackathon"
WORKFLOW = "paper-trading.yml"
ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "pending", "requested"}


def ensure_worker(github, clock: dict, *, dispatch: bool = False) -> dict:
    now = datetime.fromisoformat(clock["timestamp"])
    next_open = datetime.fromisoformat(clock["next_open"])
    near_open = timedelta(0) <= next_open - now <= timedelta(minutes=20)
    if not clock["is_open"] and not near_open:
        return {"status": "outside_session", "next_open": clock["next_open"]}

    path = f"/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}"
    # Query active states separately: old queued jobs must not disappear behind
    # a page of newer completed runs and cause an overlapping worker dispatch.
    active = []
    for status in sorted(ACTIVE_STATUSES):
        response = github.get(f"{path}/runs", params={"status": status, "per_page": 100})
        response.raise_for_status()
        active.extend(response.json()["workflow_runs"])
    if active:
        return {
            "status": "worker_exists",
            "runs": [{"id": run["id"], "status": run["status"]} for run in active],
        }
    if not dispatch:
        return {"status": "worker_missing", "dispatch_requested": False}

    repository = github.get(f"/repos/{REPOSITORY}")
    repository.raise_for_status()
    response = github.post(
        f"{path}/dispatches", json={"ref": repository.json()["default_branch"]}
    )
    response.raise_for_status()
    # Accepted dispatch is not proof of a running scanner or a filled order.
    return {"status": "dispatch_accepted", "worker_start_verified": False}


def github_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        timeout=15,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        check=False,
    )
    credentials = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    if result.returncode or not credentials.get("password"):
        raise ValueError("GitHub authentication unavailable; configure GH_TOKEN or Git credentials")
    return credentials["password"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if not settings.alpaca_paper or not settings.alpaca_configured:
        raise ValueError("Configured Alpaca paper credentials are required")
    with httpx.Client(timeout=20) as client:
        response = client.get(
            "https://paper-api.alpaca.markets/v2/clock",
            headers={
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key.get_secret_value(),
            },
        )
        response.raise_for_status()
        clock = response.json()
    with httpx.Client(
        base_url="https://api.github.com",
        headers={"Authorization": f"Bearer {github_token()}"},
        timeout=20,
    ) as github:
        print(json.dumps(ensure_worker(github, clock, dispatch=args.dispatch)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, httpx.HTTPError, subprocess.SubprocessError) as error:
        # Exception response bodies and credential-helper output stay private.
        print(json.dumps({"status": "check_failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None

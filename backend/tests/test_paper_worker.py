import importlib.util
from pathlib import Path

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "ensure_paper_worker", Path(__file__).resolve().parents[2] / "scripts/ensure_paper_worker.py"
)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def clock(open_market=True, timestamp="2026-09-09T09:30:00-04:00"):
    return {
        "is_open": open_market,
        "timestamp": timestamp,
        "next_open": "2026-09-09T09:30:00-04:00",
    }


def client(calls, active=False, failed=False):
    def handle(request):
        calls.append(request)
        if failed:
            return httpx.Response(503)
        if request.url.path.endswith("/runs"):
            runs = [{"id": 123, "status": "queued"}] if (
                active and request.url.params["status"] == "queued"
            ) else []
            return httpx.Response(200, json={"workflow_runs": runs})
        if request.method == "POST":
            return httpx.Response(204)
        return httpx.Response(200, json={"default_branch": "main"})

    return httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handle))


def test_closed_session_does_not_dispatch():
    calls = []
    with client(calls) as github:
        result = worker.ensure_worker(
            github, clock(False, "2026-09-09T04:30:00-04:00"), dispatch=True
        )
    assert result["status"] == "outside_session"
    assert not calls


def test_queued_worker_prevents_duplicate_dispatch():
    calls = []
    with client(calls, active=True) as github:
        result = worker.ensure_worker(github, clock(), dispatch=True)
    assert result["status"] == "worker_exists"
    assert not any(request.method == "POST" for request in calls)


def test_missing_worker_is_preview_only_by_default():
    calls = []
    with client(calls) as github:
        assert worker.ensure_worker(github, clock())["status"] == "worker_missing"
    assert not any(request.method == "POST" for request in calls)


def test_near_open_dispatches_once_without_claiming_running():
    calls = []
    with client(calls) as github:
        result = worker.ensure_worker(
            github, clock(False, "2026-09-09T09:15:00-04:00"), dispatch=True
        )
    assert result == {"status": "dispatch_accepted", "worker_start_verified": False}
    assert sum(request.method == "POST" for request in calls) == 1


def test_observation_failure_does_not_dispatch_replacement():
    calls = []
    with client(calls, failed=True) as github, pytest.raises(httpx.HTTPStatusError):
        worker.ensure_worker(github, clock(), dispatch=True)
    assert not any(request.method == "POST" for request in calls)

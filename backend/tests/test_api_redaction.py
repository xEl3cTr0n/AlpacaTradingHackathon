from unittest.mock import patch
from fastapi.testclient import TestClient

import regimeshift.main as main
from regimeshift.config import Settings, get_settings


def _settings():
    return Settings(
        _env_file=None,
        market_data_mode="demo",
        alpaca_api_key="fake-key",
        alpaca_secret_key="fake-secret",
    )


def test_api_endpoints_do_not_disclose_raw_upstream_exceptions():
    marker = "SYNTHETIC_PRIVATE_UPSTREAM_SECRET_LEAK"
    client = TestClient(main.app)
    main.app.dependency_overrides[get_settings] = _settings

    try:
        # Test /api/v1/live-tape
        with patch.object(main, "get_live_tick", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/live-tape?symbol=SPY")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Live tape request failed; retry shortly"

        # Test /api/v1/chart
        with patch.object(main, "build_market_data_provider", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/chart?symbol=SPY")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Chart data request failed; retry shortly"

        # Test /api/v1/options/chain
        with patch.object(main, "get_live_tick", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/options/chain?symbol=SPY")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Option chain request failed; retry shortly"

        # Test /api/v1/scanner/options-thesis
        with patch.object(main, "get_live_tick", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/scanner/options-thesis?symbol=SPY")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Options thesis request failed; retry shortly"

        # Test /api/v1/scanner
        with patch.object(main, "build_market_data_provider", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/scanner?limit=5")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Scanner market-data request failed; retry shortly"

        # Test /api/v1/platform
        with patch.object(main, "build_platform_provider", side_effect=RuntimeError(marker)):
            res = client.get("/api/v1/platform")
            assert res.status_code == 502
            assert marker not in res.json()["detail"]
            assert res.json()["detail"] == "Paper account request failed; retry shortly"

    finally:
        main.app.dependency_overrides.clear()

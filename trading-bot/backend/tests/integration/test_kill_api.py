"""Integration tests for the kill switch API endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from tests.integration.conftest import get_auth_token


@pytest.mark.asyncio
async def test_kill_global_requires_auth(client: AsyncClient):
    resp = await client.post("/api/kill/", json={"scope": "global"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kill_global_succeeds(client: AsyncClient, regular_user):
    token = await get_auth_token(client, "testuser", "UserPass1!")

    # Mock KillSwitch.execute_global to avoid real broker calls
    from app.core.kill_switch import KillResult
    from datetime import datetime, timezone
    mock_result = KillResult(
        scope="global",
        positions_closed=0,
        orders_cancelled=0,
        timestamp=datetime.now(timezone.utc),
    )
    with patch("app.api.endpoints.kill.KillSwitch") as MockKS:
        instance = MockKS.return_value
        instance.execute_global = AsyncMock(return_value=mock_result)
        resp = await client.post(
            "/api/kill/",
            json={"scope": "global"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "global"


@pytest.mark.asyncio
async def test_kill_instrument_missing_instrument_returns_422(client: AsyncClient, regular_user):
    token = await get_auth_token(client, "testuser", "UserPass1!")
    resp = await client.post(
        "/api/kill/",
        json={"scope": "instrument"},  # missing instrument field
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kill_trade_missing_trade_id_returns_422(client: AsyncClient, regular_user):
    token = await get_auth_token(client, "testuser", "UserPass1!")
    resp = await client.post(
        "/api/kill/",
        json={"scope": "trade", "instrument": "NIFTY"},  # missing trade_id
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

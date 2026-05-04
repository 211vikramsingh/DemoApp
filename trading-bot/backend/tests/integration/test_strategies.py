"""Integration tests for strategy endpoints."""
import pytest
from httpx import AsyncClient
from tests.integration.conftest import get_auth_token


@pytest.mark.asyncio
async def test_create_strategy(client: AsyncClient, regular_user):
    token = await get_auth_token(client, "testuser", "UserPass1!")
    resp = await client.post(
        "/api/strategies/",
        json={
            "name": "Nifty EMA Cross",
            "config": {"fast_ema": 9, "short_ema": 21},
            "automation_mode": "semi_auto",
            "wallet_type": "paper",
            "position_sizing_method": "half_kelly",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Nifty EMA Cross"
    assert data["wallet_type"] == "paper"


@pytest.mark.asyncio
async def test_list_strategies(client: AsyncClient, regular_user):
    token = await get_auth_token(client, "testuser", "UserPass1!")
    # Create two strategies
    for name in ["Strategy A", "Strategy B"]:
        await client.post(
            "/api/strategies/",
            json={
                "name": name,
                "config": {},
                "automation_mode": "manual",
                "wallet_type": "paper",
                "position_sizing_method": "fixed",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    resp = await client.get("/api/strategies/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_strategies_isolated_between_users(client: AsyncClient, admin_user, regular_user):
    """User cannot see another user's strategies."""
    admin_token = await get_auth_token(client, "testadmin", "AdminPass1!")
    user_token = await get_auth_token(client, "testuser", "UserPass1!")

    await client.post(
        "/api/strategies/",
        json={"name": "Admin Strategy", "config": {}, "automation_mode": "manual",
              "wallet_type": "paper", "position_sizing_method": "fixed"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = await client.get("/api/strategies/", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0

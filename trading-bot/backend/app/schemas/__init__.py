from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, EmailStr, field_validator


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Literal["admin", "trader"] = "trader"


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str


# ── Strategy ─────────────────────────────────────────────────────────────────

class StrategyCreate(BaseModel):
    name: str
    config: dict = {}
    automation_mode: Literal["auto", "semi_auto", "manual"] = "semi_auto"
    wallet_type: Literal["paper", "real"] = "paper"
    position_sizing_method: Literal["kelly", "half_kelly", "fixed"] = "half_kelly"


class StrategyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    config: dict
    automation_mode: str
    wallet_type: str
    position_sizing_method: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StrategyToggle(BaseModel):
    is_active: bool


# ── Signal ────────────────────────────────────────────────────────────────────

class SignalRead(BaseModel):
    id: uuid.UUID
    strategy_id: uuid.UUID
    instrument: str
    direction: str
    entry: Decimal
    stop_loss: Decimal
    target: Decimal
    rr_ratio: Decimal
    confidence_score: int | None
    status: str
    block_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Trade ─────────────────────────────────────────────────────────────────────

class TradeRead(BaseModel):
    id: uuid.UUID
    instrument: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal | None
    stop_loss: Decimal
    target: Decimal
    quantity: int
    status: str
    wallet_type: str
    pnl: Decimal | None
    slippage: Decimal | None
    created_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


# ── Kill Switch ───────────────────────────────────────────────────────────────

class KillRequest(BaseModel):
    scope: Literal["global", "instrument", "trade"]
    instrument: str | None = None
    trade_id: str | None = None

    @field_validator("instrument")
    @classmethod
    def instrument_required_for_scope(cls, v: str | None, info) -> str | None:
        if info.data.get("scope") == "instrument" and not v:
            raise ValueError("instrument is required for scope='instrument'")
        return v

    @field_validator("trade_id")
    @classmethod
    def trade_id_required_for_scope(cls, v: str | None, info) -> str | None:
        if info.data.get("scope") == "trade" and not v:
            raise ValueError("trade_id is required for scope='trade'")
        return v


class KillResponse(BaseModel):
    scope: str
    positions_closed: int
    orders_cancelled: int
    timestamp: datetime
    instrument: str | None = None
    trade_id: str | None = None


# ── Wallet ────────────────────────────────────────────────────────────────────

class WalletRead(BaseModel):
    id: uuid.UUID
    wallet_type: str
    currency: str
    balance: Decimal
    initial_balance: Decimal

    model_config = {"from_attributes": True}

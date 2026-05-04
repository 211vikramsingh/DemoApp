"""Strategy CRUD and activation toggle."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, HTTPException, status, Response
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser
from app.models.strategy import Strategy
from app.schemas import StrategyCreate, StrategyRead, StrategyToggle
from app.workers.strategy_worker import run_strategy, stop_strategy

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("/", response_model=StrategyRead, status_code=status.HTTP_201_CREATED)
async def create_strategy(body: StrategyCreate, db: DBSession, user: CurrentUser) -> StrategyRead:
    strat = Strategy(
        user_id=user.id,
        name=body.name,
        config=body.config,
        automation_mode=body.automation_mode,
        wallet_type=body.wallet_type,
        position_sizing_method=body.position_sizing_method,
    )
    db.add(strat)
    await db.commit()
    await db.refresh(strat)
    return StrategyRead.model_validate(strat)


@router.get("/", response_model=list[StrategyRead])
async def list_strategies(db: DBSession, user: CurrentUser) -> list[StrategyRead]:
    result = await db.execute(select(Strategy).where(Strategy.user_id == user.id))
    return [StrategyRead.model_validate(s) for s in result.scalars().all()]


@router.get("/{strategy_id}", response_model=StrategyRead)
async def get_strategy(strategy_id: uuid.UUID, db: DBSession, user: CurrentUser) -> StrategyRead:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    )
    strat = result.scalars().first()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyRead.model_validate(strat)


@router.patch("/{strategy_id}/toggle", response_model=StrategyRead)
async def toggle_strategy(
    strategy_id: uuid.UUID,
    body: StrategyToggle,
    db: DBSession,
    user: CurrentUser,
) -> StrategyRead:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    )
    strat = result.scalars().first()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strat.is_active = body.is_active
    await db.commit()
    await db.refresh(strat)

    if body.is_active:
        run_strategy.apply_async(
            args=[str(strategy_id), str(user.id)], queue="default"
        )
    else:
        stop_strategy.apply_async(
            args=[str(strategy_id), str(user.id)], queue="default"
        )

    return StrategyRead.model_validate(strat)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(strategy_id: uuid.UUID, db: DBSession, user: CurrentUser) -> Response:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    )
    strat = result.scalars().first()
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await db.delete(strat)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

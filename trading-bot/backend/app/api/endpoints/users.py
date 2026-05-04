"""User management endpoints (admin only for create/list; self for profile)."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, HTTPException, status, Response
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser, AdminUser
from app.core.security import hash_password
from app.models.user import User
from app.schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: DBSession, _: AdminUser) -> UserRead:
    existing = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/", response_model=list[UserRead])
async def list_users(db: DBSession, _: AdminUser) -> list[UserRead]:
    result = await db.execute(select(User))
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(user_id: uuid.UUID, db: DBSession, _: AdminUser) -> Response:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

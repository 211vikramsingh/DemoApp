from fastapi import APIRouter
from app.api.endpoints import auth, users, strategies, kill, ws

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(strategies.router)
router.include_router(kill.router)
router.include_router(ws.router)

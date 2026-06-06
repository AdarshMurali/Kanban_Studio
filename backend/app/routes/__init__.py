from fastapi import APIRouter

from app.routes import board, chat, auth, static

api_router = APIRouter()
api_router.include_router(board.router)
api_router.include_router(chat.router)
api_router.include_router(auth.router)

static_router = static.router

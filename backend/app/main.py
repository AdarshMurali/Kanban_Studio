from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.database import init_db
from app.routes import api_router, static_router
from app.routes.static import get_static_dir
from app.logging_config import app_logger
from app.rate_limit import limiter as rate_limiter, rate_limit_exceeded_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Starting up application")
    init_db()
    app_logger.info("Database initialized")

    # Setup rate limiting
    app.state.limiter = rate_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app_logger.info("Rate limiting initialized")

    yield
    app_logger.info("Shutting down application")


app = FastAPI(lifespan=lifespan)


def _mount_static_assets(static_dir) -> None:
    next_assets = static_dir / "_next"
    if next_assets.exists():
        app.mount("/_next", StaticFiles(directory=next_assets), name="next-assets")
    static_assets = static_dir / "static"
    if static_assets.exists():
        app.mount("/static", StaticFiles(directory=static_assets), name="static-assets")


STATIC_DIR = get_static_dir()
if STATIC_DIR:
    _mount_static_assets(STATIC_DIR)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict:
    return {"message": "Hello from FastAPI"}


app.include_router(api_router)
app.include_router(static_router)

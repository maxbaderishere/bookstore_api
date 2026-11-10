from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401, RUF100
from app.core.exception_handlers import register_exception_handlers
from app.db.base import init_db
from app.db.redis import close_redis
from app.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_redis()


app = FastAPI(lifespan=lifespan, title="BookStoreApi")
register_exception_handlers(app)
app.include_router(api_router)

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401, RUF100
from app.db.base import init_db
from app.db.redis import close_redis
from app.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_redis()


app = FastAPI(lifespan=lifespan, title="BookStoreApi")
app.include_router(api_router)

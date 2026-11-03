from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401, RUF100
from app.db.base import init_db
from app.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan, title="BookStoreApi")
app.include_router(api_router)

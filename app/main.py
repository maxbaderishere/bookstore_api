from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401, RUF100
from app.db.base import engine
from app.models.base import Base
from app.routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="BookStoreApi")
app.include_router(api_router)




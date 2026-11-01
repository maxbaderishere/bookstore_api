from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

import app.models  # noqa: F401, RUF100
from app.models.base import Base, engine, session_maker


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

#BookDep = Annotated[..., Depends(...)]


@app.get("/books")
async def get_books():
    return "in progress"


@app.get("/books/{book_id}")
async def show_book():
    return "in progress"


@app.post("/books")
async def create_book():
    return "in progress"

@app.patch("/books/{book_id}")
async def change_book():
    return "in progress"


@app.delete("/books/{book_id}")
async def delete_book():
    pass

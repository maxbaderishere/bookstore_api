from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession


async def fetch_by_ids(db: DbSession, model, ids: list[int], name: str) -> list:
    unique_ids = set(ids)
    result = await db.execute(select(model).where(model.id.in_(unique_ids)))
    items = list(result.scalars().all())
    if len(items) != len(unique_ids):
        raise HTTPException(status_code=404, detail=f"Some {name} not found")
    return items


async def commit_or_409(db: DbSession) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict: a book with such unique data (e.g. ISBN) already exists",
        )

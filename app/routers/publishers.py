from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.dependencies import AdminUser, BookCacheDep, DbSession
from app.models.publisher import Publisher
from app.routers.utils import commit_or_409
from app.schemas.publisher import PublisherCreate, PublisherOut, PublisherUpdate

router = APIRouter(prefix="/publishers", tags=["publishers"])


def publisher_query():
    return select(Publisher).options(
        joinedload(Publisher.name).selectinload(Publisher.id)
    )


async def load_publisher(
    db: DbSession,
    publisher_id: int,
    *,
    refresh: bool = False,
):
    stmt = select(Publisher).where(Publisher.id == publisher_id)
    if refresh:
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.get("", response_model=list[PublisherOut])
async def get_publishers(
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Publisher).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{publisher_id}", response_model=PublisherOut)
async def show_publisher(
    db: DbSession,
    publisher_id: int,
):
    publisher = await load_publisher(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="There is no such publisher")
    return publisher


@router.post("", response_model=PublisherOut, status_code=201)
async def create_publisher(db: DbSession, _: AdminUser, data: PublisherCreate):
    publisher = Publisher(**data.model_dump())

    db.add(publisher)
    await commit_or_409(db)

    return publisher


@router.patch("/{publisher_id}", response_model=PublisherOut)
async def change_publisher(
    db: DbSession,
    cache: BookCacheDep,
    _: AdminUser,
    publisher_id: int,
    data: PublisherUpdate,
):
    publisher = await db.get(Publisher, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="There is no such publisher")

    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(publisher, field, value)

    await commit_or_409(db)
    await cache.invalidate()
    await db.refresh(publisher)
    return publisher


@router.delete("/{publisher_id}", status_code=204)
async def delete_publisher(
    db: DbSession, cache: BookCacheDep, _: AdminUser, publisher_id: int
):
    publisher = await db.get(Publisher, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="There is no such publisher")
    await db.delete(publisher)
    await db.commit()
    await cache.invalidate()

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.dependencies import AdminUser, BookCacheDep, DbSession
from app.models.author import Author
from app.routers.utils import commit_or_409
from app.schemas.author import AuthorCreate, AuthorOut, AuthorUpdate

router = APIRouter(prefix="/authors", tags=["authors"])

NOT_NULLABLE = {"full_name"}


def author_query():
    return select(Author).options(
        joinedload(Author.full_name),
        selectinload(Author.bio),
        selectinload(Author.birth_year),
    )


async def load_author(
    db: DbSession, author_id: int, *, refresh: bool = False
) -> Author | None:
    stmt = select(Author).where(Author.id == author_id)
    if refresh:
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.get("", response_model=list[AuthorOut])
async def get_authors(
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Author).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{author_id}", response_model=AuthorOut)
async def show_author(
    db: DbSession,
    author_id: int,
):
    author = await load_author(db, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="There is no such author")
    return author


@router.post("", response_model=AuthorOut, status_code=201)
async def create_author(db: DbSession, _: AdminUser, data: AuthorCreate):
    author = Author(**data.model_dump())

    db.add(author)
    await commit_or_409(db)

    return author


@router.patch("/{author_id}", response_model=AuthorOut)
async def change_author(
    db: DbSession, cache: BookCacheDep, _: AdminUser, author_id: int, data: AuthorUpdate
):
    author = await db.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="There is no such author")

    changes = data.model_dump(exclude_unset=True)

    for field in NOT_NULLABLE & changes.keys():
        if changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")

    for field, value in changes.items():
        setattr(author, field, value)

    await commit_or_409(db)
    await cache.invalidate()
    await db.refresh(author)
    return author


@router.delete("/{author_id}", status_code=204)
async def delete_book(db: DbSession, cache: BookCacheDep, _: AdminUser, author_id: int):
    author = await db.get(Author, author_id)
    if Author is None:
        raise HTTPException(status_code=404, detail="There is no such author")
    await db.delete(author)
    await db.commit()
    await cache.invalidate()

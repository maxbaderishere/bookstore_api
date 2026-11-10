from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.dependencies import AdminUser, BookCacheDep, DbSession
from app.models.author import Author
from app.models.book import Book
from app.models.genre import Genre
from app.models.publisher import Publisher
from app.routers.utils import commit_or_409, fetch_by_ids
from app.schemas.book import BookCreate, BookOut, BookUpdate

router = APIRouter(prefix="/books", tags=["books"])

NOT_NULLABLE = {
    "title",
    "isbn",
    "price",
    "stock",
    "publication_year",
    "language",
    "pages",
}


def book_query():
    return select(Book).options(
        joinedload(Book.publisher),
        selectinload(Book.authors),
        selectinload(Book.genres),
    )


async def ensure_publisher(db: DbSession, publisher_id: int) -> None:
    if await db.get(Publisher, publisher_id) is None:
        raise HTTPException(status_code=404, detail="Publisher not found")


async def load_book(
    db: DbSession, book_id: int, *, refresh: bool = False
) -> Book | None:
    stmt = book_query().where(Book.id == book_id)
    if refresh:
        # перечитать данные, даже если объект уже есть в сессии
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def set_cache_header(response: Response, hit: bool) -> None:
    response.headers["X-Cache"] = "HIT" if hit else "MISS"


@router.get("", response_model=list[BookOut])
async def get_books(
    db: DbSession,
    cache: BookCacheDep,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async def load() -> list[dict]:
        stmt = book_query().order_by(Book.id).limit(limit).offset(offset)
        books = (await db.execute(stmt)).scalars().all()
        return [BookOut.model_validate(b).model_dump(mode="json") for b in books]

    data, hit = await cache.get_or_load(cache.list_key(limit, offset), load)
    set_cache_header(response, hit)
    return data


@router.get("/{book_id}", response_model=BookOut)
async def show_book(
    db: DbSession, cache: BookCacheDep, response: Response, book_id: int
):
    async def load() -> dict | None:
        book = await load_book(db, book_id)
        if book is None:
            return None
        return BookOut.model_validate(book).model_dump(mode="json")

    data, hit = await cache.get_or_load(cache.book_key(book_id), load)
    if data is None:
        raise HTTPException(status_code=404, detail="There is no such book")
    set_cache_header(response, hit)
    return data


@router.post("", response_model=BookOut, status_code=201)
async def create_book(
    db: DbSession, cache: BookCacheDep, _: AdminUser, data: BookCreate
):
    values = data.model_dump()
    author_ids = values.pop("author_ids", None) or []
    genre_ids = values.pop("genre_ids", None) or []

    if values.get("publisher_id") is not None:
        await ensure_publisher(db, values["publisher_id"])

    authors = await fetch_by_ids(db, Author, author_ids, "authors")
    genres = await fetch_by_ids(db, Genre, genre_ids, "genres")
    book = Book(**values, authors=authors, genres=genres)

    db.add(book)
    await commit_or_409(db)
    await cache.invalidate()

    return await load_book(db, book.id, refresh=True)


@router.patch("/{book_id}", response_model=BookOut)
async def change_book(
    db: DbSession, cache: BookCacheDep, _: AdminUser, book_id: int, data: BookUpdate
):
    book = await load_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="There is no such book")

    changes = data.model_dump(exclude_unset=True)
    author_ids = changes.pop("author_ids", None)
    genre_ids = changes.pop("genre_ids", None)

    for field in NOT_NULLABLE & changes.keys():
        if changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")

    if changes.get("publisher_id") is not None:
        await ensure_publisher(db, changes["publisher_id"])

    for field, value in changes.items():
        setattr(book, field, value)

    if author_ids is not None:
        book.authors = await fetch_by_ids(db, Author, author_ids, "authors")
    if genre_ids is not None:
        book.genres = await fetch_by_ids(db, Genre, genre_ids, "genres")

    await commit_or_409(db)
    await cache.invalidate()
    return await load_book(db, book_id, refresh=True)


@router.delete("/{book_id}", status_code=204)
async def delete_book(db: DbSession, cache: BookCacheDep, _: AdminUser, book_id: int):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="There is no such book")
    await db.delete(book)
    await commit_or_409(db, "Book has orders and cannot be deleted")
    await cache.invalidate()

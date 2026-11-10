from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.dependencies import AdminUser, DbSession
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


@router.get("", response_model=list[BookOut])
async def get_books(
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = book_query().order_by(Book.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{book_id}", response_model=BookOut)
async def show_book(db: DbSession, book_id: int):
    book = await load_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="There is no such book")
    return book


@router.post("", response_model=BookOut, status_code=201)
async def create_book(db: DbSession, _: AdminUser, data: BookCreate):
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

    return await load_book(db, book.id, refresh=True)


@router.patch("/{book_id}", response_model=BookOut)
async def change_book(db: DbSession, _: AdminUser, book_id: int, data: BookUpdate):
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
    return await load_book(db, book_id, refresh=True)


@router.delete("/{book_id}", status_code=204)
async def delete_book(db: DbSession, _: AdminUser, book_id: int):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="There is no such book")
    await db.delete(book)
    await db.commit()

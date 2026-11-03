from slugify import slugify
from sqlalchemy import select

from app.db.session import DbSession
from app.models.genre import Genre

DEFAULT_GENRES = [
    "Fantasy",
    "Science Fiction",
    "Detective",
    "Romance",
    "Horror",
    "Thriller",
    "History",
    "Biography",
    "Philosophy",
    "Psychology",
]


async def seed_database(session: DbSession):
    result = await session.execute(select(Genre))

    existing_genres = {
        genre.name for genre in result.scalars().all()
    }

    for genre_name in DEFAULT_GENRES:
        if genre_name not in existing_genres:
            session.add(
                Genre(
                    name=genre_name,
                    slug=slugify(genre_name)
                )
            )

    await session.commit()
from fastapi import APIRouter

from . import authors, books

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(books.router)
api_router.include_router(authors.router)
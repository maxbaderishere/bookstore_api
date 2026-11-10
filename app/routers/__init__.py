from fastapi import APIRouter

from . import auth, authors, books, cart, publishers

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(books.router)
api_router.include_router(authors.router)
api_router.include_router(publishers.router)
api_router.include_router(cart.router)

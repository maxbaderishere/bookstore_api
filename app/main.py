from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

app = FastAPI()

BookDep = Annotated[..., Depends(...)]


@app.get("/books")
async def get_books():
    pass


@app.get("/books/{book_id}")
async def show_book():
    pass


@app.post("/books")
async def create_book():
    pass


@app.patch("/books/{book_id}")
async def change_book():
    pass


@app.delete("/books/{book_id}")
async def delete_book():
    pass

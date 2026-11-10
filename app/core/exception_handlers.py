from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, ConflictError, NotFoundError

STATUS_BY_ERROR: dict[type[AppError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    code = next(
        (code for cls, code in STATUS_BY_ERROR.items() if isinstance(exc, cls)),
        status.HTTP_400_BAD_REQUEST,
    )
    return JSONResponse(status_code=code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)

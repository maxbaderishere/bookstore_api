"""Кэш ответов GET /books и GET /books/{id} в Redis.

Инвалидация через версию: все ключи книг содержат текущее значение счётчика
`books:version`. Любое изменение книг, авторов или издателей увеличивает
счётчик, и старые ключи просто перестают читаться (их удалит TTL).
Так не нужно искать и удалять ключи списков через SCAN.

Версия фиксируется ДО чтения из БД, и запись в кэш идёт под неё же: если
пока мы читали БД кто-то изменил данные, устаревший ответ попадёт под старую
версию и никогда не будет прочитан.

Кэш необязателен: если Redis недоступен, запросы идут в БД.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import cfg

logger = logging.getLogger(__name__)

VERSION_KEY = "books:version"

Loader = Callable[[], Awaitable[Any | None]]


class BookCache:
    def __init__(self, redis: Redis, ttl: int = cfg.CACHE_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl = ttl

    @staticmethod
    def book_key(book_id: int) -> str:
        return f"item:{book_id}"

    @staticmethod
    def list_key(limit: int, offset: int) -> str:
        return f"list:{limit}:{offset}"

    async def get_or_load(self, key: str, loader: Loader) -> tuple[Any | None, bool]:
        """Возвращает (значение, было_ли_попадание_в_кэш).

        loader вызывается при промахе; None от loader не кэшируется (например, 404).
        """
        full_key = None
        try:
            version = await self._redis.get(VERSION_KEY) or "0"
            full_key = f"books:v{version}:{key}"
            raw = await self._redis.get(full_key)
            if raw is not None:
                return json.loads(raw), True
        except RedisError:
            logger.warning("Redis unavailable, reading books from DB", exc_info=True)
            full_key = None

        value = await loader()

        if value is not None and full_key is not None:
            try:
                await self._redis.set(full_key, json.dumps(value), ex=self._ttl)
            except RedisError:
                logger.warning("Redis unavailable, skipping cache write", exc_info=True)

        return value, False

    async def invalidate(self) -> None:
        try:
            await self._redis.incr(VERSION_KEY)
        except RedisError:
            # Без инвалидации данные могут быть устаревшими не дольше TTL.
            logger.exception("Redis unavailable, books cache not invalidated")

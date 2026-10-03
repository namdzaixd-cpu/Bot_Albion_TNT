"""
config_store.py — Centralized, cached config access layer.

Vấn đề cũ: mỗi cog tự query Supabase riêng → N query trùng lặp, không cache,
không invalidate thống nhất.

Giải pháp:
- Single in-memory cache per (table, guild_id).
- Load lazy; chỉ row thiếu được dùng default, DB lỗi không cache.
- Invalidate khi dashboard PATCH (bot webhook → on_config_reload).
- Runtime gọi các async boundary, không query trong constructor cog.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import logging
import threading
from typing import Any, Callable

from .config import GUILD_ID
from .db import DBError, safe_select, safe_upsert

logger = logging.getLogger("bot.config_store")

_cache: dict[tuple[str, str], Any] = {}
_cache_lock = threading.Lock()
_enabled = True  # tắt cache nếu muốn luôn đọc tươi
_generation = 0


def get_config(table: str, guild_id: str | None = None,
               default: Any | Callable[[], Any] = None,
               id_column: str = "guild_id") -> Any:
    """Không trả/cache default khi SELECT thất bại."""
    gid = str(guild_id or GUILD_ID)
    key = (table, gid)
    while True:
        with _cache_lock:
            generation = _generation
            if _enabled and key in _cache:
                return deepcopy(_cache[key])
        data, error = safe_select(table, columns="*",
                                  filters={id_column: gid}, single=True)
        if error:
            raise DBError(f"Không đọc được {table}/{gid}: {error}")
        if data is None:
            data = default() if callable(default) else deepcopy(default)
        with _cache_lock:
            if generation != _generation:
                continue
            _cache[key] = deepcopy(data)
            return data


def save_config(table: str, row: dict, *,
                id_column: str = "guild_id",
                on_conflict: str | None = None) -> bool:
    """Commit trước khi cập nhật cache; lỗi không mutate cache."""
    global _generation
    gid = str(row[id_column])
    snapshot = deepcopy(row)
    error = safe_upsert(table, snapshot, on_conflict=on_conflict or id_column)
    if error:
        raise DBError(f"Không ghi được {table}/{gid}: {error}")
    with _cache_lock:
        _generation += 1
        _cache.pop((table, gid), None)
    return True


def invalidate(table: str | None = None, guild_id: str | None = None) -> None:
    """Xoá cache. Gọi khi dashboard đổi config."""
    global _generation
    gid = str(guild_id or GUILD_ID) if guild_id else None
    with _cache_lock:
        _generation += 1
        if table is None and gid is None:
            _cache.clear()
        else:
            keys = [k for k in _cache if (table is None or k[0] == table)
                    and (gid is None or k[1] == gid)]
            for k in keys:
                del _cache[k]
    logger.info("Config cache invalidated (table=%s, guild=%s)", table, gid)


async def get_config_async(table: str, guild_id: str | None = None,
                           default: Any | Callable[[], Any] = None,
                           id_column: str = "guild_id") -> Any:
    return await asyncio.to_thread(get_config, table, guild_id,
                                   default, id_column)


async def save_config_async(table: str, row: dict, *,
                            id_column: str = "guild_id",
                            on_conflict: str | None = None) -> bool:
    snapshot = deepcopy(row)
    return await asyncio.to_thread(save_config, table, snapshot,
                                   id_column=id_column, on_conflict=on_conflict)

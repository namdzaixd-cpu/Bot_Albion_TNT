"""
storage.py — JSON blob storage trên Supabase (bảng json_storage).

Chỉ row không tồn tại mới dùng default. Lỗi đọc/ghi được truyền tới caller;
runtime dùng async boundary để không giữ event loop và ghi snapshot nhất quán.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from typing import Any, Callable

from .db import DBError, safe_select, safe_upsert


TABLE = "json_storage"


def load_json(path: str, default: Any | Callable[[], Any]) -> Any:
    """Đọc blob; DB lỗi không được hiểu là kho rỗng."""
    filename = os.path.basename(path)
    data, error = safe_select(TABLE, columns="data",
                              filters={"file_name": filename}, single=True)
    if error:
        raise DBError(f"Không đọc được {filename}: {error}")
    if data is None:
        return default() if callable(default) else deepcopy(default)
    return data["data"] if isinstance(data, dict) and "data" in data else data


def save_json(data: Any, path: str) -> bool:
    """Lưu blob hoặc raise; không báo success khi persist thất bại."""
    filename = os.path.basename(path)
    if not isinstance(data, (dict, list)):
        raise TypeError(f"{filename}: data phải là dict/list")
    json.dumps(data)
    error = safe_upsert(TABLE, {"file_name": filename, "data": data},
                        on_conflict="file_name")
    if error:
        raise DBError(f"Không ghi được {filename}: {error}")
    return True


async def load_json_async(path: str, default: Any | Callable[[], Any]) -> Any:
    return await asyncio.to_thread(load_json, path, default)


async def save_json_async(data: Any, path: str) -> bool:
    snapshot = deepcopy(data)
    return await asyncio.to_thread(save_json, snapshot, path)



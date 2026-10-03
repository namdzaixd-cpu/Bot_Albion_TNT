"""
db.py — Supabase client wrapper chuẩn cho backend (bot).

Thiết kế:
- Lazy init: client chỉ tạo khi thực sự dùng (tránh crash lúc import nếu thiếu env).
- SELECT có retry/backoff; mutation không retry mù khi kết quả chưa rõ.
- Timeout PostgREST được cấu hình trên client.
- Structured logging không lộ credential.
- Helper trả (data, error); storage/config truyền lỗi thay vì default giả.

Runtime dùng async_execute; sync helper chỉ dành cho scripts ngoài event loop.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from typing import Any, Callable, Optional, TypeVar

try:
    from supabase import Client, ClientOptions, create_client
    from postgrest import SyncMaybeSingleRequestBuilder
except ImportError:
    Client = Any  # type: ignore
    create_client = None  # type: ignore
    ClientOptions = None  # type: ignore
    SyncMaybeSingleRequestBuilder = ()  # type: ignore
from .config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger("bot.db")

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5  # giây, nhân đôi mỗi lần
DEFAULT_TIMEOUT = 10.0  # giây

T = TypeVar("T")


class DBError(Exception):
    """Lỗi tầng DB (sau khi đã retry hết số lần)."""


_client: Optional[Client] = None
_initialized = False

_client_lock = threading.Lock()


def _error_message(error: Any) -> str:
    message = str(error)
    if SUPABASE_KEY:
        message = message.replace(SUPABASE_KEY, "[redacted]")
    return re.sub(r"(postgres(?:ql)?://)[^@\s]+@", r"\1[redacted]@", message)

def get_client() -> Optional[Client]:
    """Khởi tạo client một lần; timeout áp dụng thật cho PostgREST."""
    global _client, _initialized
    with _client_lock:
        if _initialized:
            return _client
        _initialized = True
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("SUPABASE_URL/KEY chưa cấu hình — DB bị disable.")
            return None
        if create_client is None:
            logger.error("Thiếu thư viện supabase.")
            return None
        try:
            options = ClientOptions(postgrest_client_timeout=DEFAULT_TIMEOUT)
            _client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
        except Exception as exc:
            logger.error("Không thể khởi tạo Supabase client: %s", _error_message(exc))
        return _client


def _with_retry(fn: Callable[[], T], *, retries: int = DEFAULT_RETRIES,
               backoff: float = DEFAULT_BACKOFF) -> T:
    """Chạy fn, tự retry nếu raise. Raise DBError sau khi hết retries."""
    if retries < 1:
        raise ValueError("retries phải là số lần thử >= 1")
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait = backoff * (2 ** (attempt - 1))
            logger.warning(
                "DB call thất bại (lần %d/%d): %s — retry sau %.2fs",
                attempt, retries, _error_message(exc), wait,
            )
            if attempt < retries:
                time.sleep(wait)
    raise DBError(f"DB call failed after {retries} attempts: {_error_message(last_exc)}")


# ── High-level helpers ──────────────────────────────────────────────────────

def safe_select(table: str, *, columns: str = "*",
                filters: Optional[dict] = None,
                single: bool = False) -> tuple[Optional[Any], Optional[str]]:
    """SELECT an toàn. Trả (data, error_msg). error_msg=None nếu OK."""
    client = get_client()
    if client is None:
        return (None, "client_unavailable")
    try:
        query = client.table(table).select(columns)
        for k, v in (filters or {}).items():
            query = query.eq(k, v)
        if single:
            query = query.maybe_single()
        res = _with_retry(lambda: query.execute())
        if res is None:
            return (None, None) if single else (None, "query_returned_none")
        if getattr(res, "error", None):
            return (None, _error_message(res.error))
        return (res.data, None)
    except DBError as e:
        return (None, _error_message(e))
    except Exception as e:
        logger.error("safe_select: %s", _error_message(e))
        return (None, _error_message(e))


def safe_upsert(table: str, row: dict, *,
                on_conflict: Optional[str] = None) -> Optional[str]:
    """UPSERT an toàn. Trả error_msg (None nếu OK)."""
    client = get_client()
    if client is None:
        return "client_unavailable"
    try:
        query = client.table(table).upsert(row, on_conflict=on_conflict or "")
        res = query.execute()
        if res is None:
            return "query_returned_none"
        if getattr(res, "error", None):
            return _error_message(res.error)
        return None
    except Exception as e:
        logger.error("safe_upsert: %s", _error_message(e))
        return _error_message(e)


def safe_insert(table: str, row: dict) -> Optional[str]:
    client = get_client()
    if client is None:
        return "client_unavailable"
    try:
        res = client.table(table).insert(row).execute()
        if res is None:
            return "query_returned_none"
        if getattr(res, "error", None):
            return _error_message(res.error)
        return None
    except Exception as e:
        logger.error("safe_insert: %s", _error_message(e))
        return _error_message(e)


def safe_update(table: str, row: dict, *,
                filters: dict) -> Optional[str]:
    client = get_client()
    if client is None:
        return "client_unavailable"
    try:
        query = client.table(table).update(row)
        for k, v in filters.items():
            query = query.eq(k, v)
        res = query.execute()
        if res is None:
            return "query_returned_none"
        if getattr(res, "error", None):
            return _error_message(res.error)
        return None
    except Exception as e:
        logger.error("safe_update: %s", _error_message(e))
        return _error_message(e)


def execute(query_builder: Callable[[Client], Any], *,
            retries: int = 1) -> tuple[Optional[Any], Optional[str]]:
    """Execute một query chưa gửi; không retry mutation mặc định."""
    client = get_client()
    if client is None:
        return (None, "client_unavailable")
    try:
        query = query_builder(client)
        res = _with_retry(query.execute, retries=retries)
        if res is None:
            return (None, None) if isinstance(query, SyncMaybeSingleRequestBuilder) else (None, "query_returned_none")
        if getattr(res, "error", None):
            return (None, _error_message(res.error))
        return (res, None)
    except Exception as exc:
        return (None, _error_message(exc))


async def async_execute(query_builder: Callable[[Client], Any], *,
                        retries: int = 1) -> tuple[Optional[Any], Optional[str]]:
    """Chạy query trong worker thread, không giữ event loop Discord."""
    return await asyncio.to_thread(execute, query_builder, retries=retries)


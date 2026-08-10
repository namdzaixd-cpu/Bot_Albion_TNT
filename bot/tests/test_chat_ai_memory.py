"""Test giới hạn bộ nhớ chat_ai (chống OOM Render ~512MB) — không cần Discord thật / Supabase.

Che 4 nhóm:
  A. __init__ khởi tạo _summary_pending / _scan_ocr_count (trước đây chưa khởi tạo
     `_summary_pending` → AttributeError khi có request tóm tắt không-cache).
  B. _reload_config(force=False) throttle: không gọi DB mỗi tin nhắn trong TTL,
     vẫn reload khi hết hạn; force=True luôn reload (giữ nguyên hành vi lệnh admin).
  C. _should_debounce: debounce 8s + prune entry cũ khi dict vượt _SUMMARY_PENDING_MAX.
  D. _process_msg_for_docs: chặn nhận thêm docs / OCR khi chạm trần (chống bung RAM khi quét).

Mock nội bộ unittest để deterministic, không gọi network.
"""
import asyncio
import time
from unittest import mock


def _make_cog():
    from cogs.chat_ai import ChatAI
    return ChatAI(mock.Mock())


# ---------- A. Khởi tạo ----------
def test_init_has_memory_guards():
    cog = _make_cog()
    assert cog._summary_pending == {}
    assert cog._scan_ocr_count == 0


# ---------- B. Throttle reload config ----------
def test_reload_config_throttle_skips_db_within_ttl():
    from cogs import chat_ai as mod

    cog = _make_cog()
    cog._config_loaded_ts = time.time()  # vừa reload trong TTL
    with mock.patch.object(mod, "execute") as exe:
        cog._reload_config(force=False)
        assert exe.call_count == 0  # bỏ qua Supabase/library


def test_reload_config_throttle_reloads_when_expired():
    from cogs import chat_ai as mod

    cog = _make_cog()
    cog._config_loaded_ts = time.time() - 1000  # hết hạn TTL
    with mock.patch.object(mod, "execute") as exe:
        cog._reload_config(force=False)
        assert exe.call_count >= 1


def test_reload_config_force_always_reloads():
    from cogs import chat_ai as mod

    cog = _make_cog()
    cog._config_loaded_ts = time.time()  # dù mới reload, force vẫn reload
    with mock.patch.object(mod, "execute") as exe:
        cog._reload_config(force=True)
        assert exe.call_count >= 1


# ---------- C. Debounce + prune ----------
def test_should_debounce_initial_false_then_true():
    cog = _make_cog()
    assert cog._should_debounce("c|24") is False  # lần đầu
    assert cog._should_debounce("c|24") is True   # lặp trong 8s → debounce


def test_should_debounce_prunes_stale_entries():
    from cogs.chat_ai import _SUMMARY_PENDING_MAX

    cog = _make_cog()
    stale_ts = time.time() - 1000  # cũ hơn _SUMMARY_PENDING_TTL (120s)
    for i in range(_SUMMARY_PENDING_MAX + 100):
        cog._summary_pending[f"stale{i}"] = stale_ts
    cog._should_debounce("fresh")
    # toàn bộ entry cũ bị dọn; chỉ còn key vừa thêm
    assert len(cog._summary_pending) == 1
    assert "fresh" in cog._summary_pending


# ---------- D. Trần quét thư viện ----------
def test_process_msg_for_docs_caps_total_docs():
    from cogs.chat_ai import LIBRARY_SCAN_MAX_DOCS

    cog = _make_cog()
    docs = [{} for _ in range(LIBRARY_SCAN_MAX_DOCS)]  # đã chạm trần docs
    att = mock.Mock(content_type="image/png", url="http://x/i.png")
    msg = mock.Mock(content="hello", attachments=[att])
    asyncio.run(cog._process_msg_for_docs(msg, "t", docs))
    assert len(docs) == LIBRARY_SCAN_MAX_DOCS  # không append thêm
    assert cog._scan_ocr_count == 0


def test_process_msg_for_docs_caps_ocr():
    from cogs.chat_ai import LIBRARY_SCAN_MAX_OCR

    cog = _make_cog()
    cog._scan_ocr_count = LIBRARY_SCAN_MAX_OCR  # đã hết budget OCR
    att = mock.Mock(content_type="image/png", url="http://x/i.png")
    msg = mock.Mock(content="hello", attachments=[att])
    asyncio.run(cog._process_msg_for_docs(msg, "t", []))
    # dừng sớm, không OCR thêm
    assert cog._scan_ocr_count == LIBRARY_SCAN_MAX_OCR
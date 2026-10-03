import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from types import SimpleNamespace

import pytest

from core import config_store, db, storage


def test_failed_blob_read_is_not_an_empty_store(monkeypatch):
    monkeypatch.setattr(storage, "safe_select", lambda *a, **k: (None, "timeout"))
    with pytest.raises(db.DBError):
        storage.load_json("tnc_templates_v1.json", dict)


def test_failed_config_read_does_not_poison_future_reads(monkeypatch):
    config_store.invalidate()
    responses = iter([(None, "timeout"), ({"guild_id": "test", "channel": "new"}, None)])
    monkeypatch.setattr(config_store, "safe_select", lambda *a, **k: next(responses))
    with pytest.raises(db.DBError):
        config_store.get_config("guild_config", "test", default={"channel": "old"})
    assert config_store.get_config("guild_config", "test")["channel"] == "new"
    config_store.invalidate()


def test_reload_cannot_resurrect_an_inflight_stale_config(monkeypatch):
    config_store.invalidate()
    started, release = Event(), Event()
    calls = 0

    def select(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            assert release.wait(2)
            return {"guild_id": "test", "channel": "old"}, None
        return {"guild_id": "test", "channel": "new"}, None

    monkeypatch.setattr(config_store, "safe_select", select)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(config_store.get_config, "guild_config", "test")
        try:
            assert started.wait(2)
            config_store.invalidate("guild_config", "test")
        finally:
            release.set()
        assert result.result(timeout=2)["channel"] == "new"
    assert config_store.get_config("guild_config", "test")["channel"] == "new"
    config_store.invalidate()


def test_config_edits_do_not_mutate_cached_authoritative_data(monkeypatch):
    config_store.invalidate()
    monkeypatch.setattr(config_store, "safe_select", lambda *a, **k: (
        {"guild_id": "test", "emoji_map": {"green": {"value": 100}}}, None
    ))
    edited = config_store.get_config("corebank_config", "test")
    edited["emoji_map"]["green"]["value"] = 200
    assert config_store.get_config("corebank_config", "test")["emoji_map"]["green"]["value"] == 100
    config_store.invalidate()


def test_async_blob_write_preserves_snapshot_during_concurrent_edits(monkeypatch):
    started, release = Event(), Event()
    persisted = []

    def upsert(table, row, **kwargs):
        started.set()
        assert release.wait(2)
        persisted.append(deepcopy(row["data"]))
        return None

    monkeypatch.setattr(storage, "safe_upsert", upsert)

    async def run():
        party = {"slots": {"DPS": [1]}}
        write = asyncio.create_task(storage.save_json_async(party, "tnc_massing_v1.json"))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            party["slots"]["DPS"].append(2)
        finally:
            release.set()
        await write
        assert persisted == [{"slots": {"DPS": [1]}}]

    asyncio.run(run())


def test_slow_database_query_does_not_stop_other_async_work(monkeypatch):
    started, release = Event(), Event()

    class Query:
        def execute(self):
            started.set()
            if not release.wait(2):
                raise RuntimeError("event loop blocked while database waited")
            return SimpleNamespace(data=None)

    monkeypatch.setattr(db, "get_client", lambda: object())

    async def run():
        async def gateway_work():
            assert await asyncio.to_thread(started.wait, 2)
            release.set()

        query = asyncio.create_task(db.async_execute(lambda client: Query()))
        await gateway_work()
        _, error = await query
        assert error is None

    asyncio.run(run())

"""Regression tests cho các lỗi tìm ra trong audit toàn dự án."""
import asyncio
from types import SimpleNamespace


def test_every_extension_is_importable_and_blacklist_is_loaded():
    import importlib

    import main

    assert "cogs.blacklist" in main.EXTENSIONS
    for name in main.EXTENSIONS:
        assert hasattr(importlib.import_module(name), "setup"), name


def test_overwrite_template_view_has_confirm_button():
    from cogs.massing import ConfirmOverwriteTemplateView

    async def build():
        view = ConfirmOverwriteTemplateView("a", "a", {})
        return [child.label for child in view.children]

    labels = asyncio.run(build())
    assert any("Ghi đè" in label for label in labels)
    assert any("Hủy" in label for label in labels)


def test_weekly_clear_wait_survives_restart():
    from cogs.massing import WEEKLY_CLEAR_SECONDS, weekly_clear_wait

    assert weekly_clear_wait(1000, 1000) == WEEKLY_CLEAR_SECONDS
    assert weekly_clear_wait(1000, 1000 + 3 * 86400) == 4 * 86400
    assert weekly_clear_wait(1000, 1000 + 30 * 86400) == 0


class _FakeQuery:
    def __init__(self, store, rows):
        self.store, self.rows, self.ops = store, rows, []

    def select(self, *a): self.ops.append(("select", a)); return self
    def eq(self, *a): self.ops.append(("eq", a)); return self
    def ilike(self, *a): self.ops.append(("ilike", a)); return self
    def delete(self): self.ops.append(("delete", ())); return self


def _fake_db(monkeypatch, rows_for):
    from cogs import blacklist

    queries = []

    class Client:
        def table(self, name):
            q = _FakeQuery(queries, None)
            queries.append(q)
            return q

    async def fake_execute(builder, **_):
        q = builder(Client())
        key = next((op for op in q.ops if op[0] in ("eq", "ilike", "delete")), None)
        return SimpleNamespace(data=rows_for(q.ops)), None

    monkeypatch.setattr(blacklist, "async_execute", fake_execute)
    return queries


def test_blacklist_remove_escapes_wildcards_and_deletes_by_key(monkeypatch):
    from cogs.blacklist import GlobalBlacklist

    queries = _fake_db(monkeypatch, lambda ops: (
        [{"discord_id": "42"}] if ("ilike", ("ingame_name", "100\\%\\_x")) in ops else []
    ))
    assert asyncio.run(GlobalBlacklist().remove_entry("100%_x")) is True
    flat = [op for q in queries for op in q.ops]
    assert ("ilike", ("ingame_name", "100\\%\\_x")) in flat
    assert ("eq", ("discord_id", "42")) in flat and ("delete", ()) in flat


def test_blacklist_remove_wildcard_only_input_never_matches_everything(monkeypatch):
    from cogs.blacklist import GlobalBlacklist

    queries = _fake_db(monkeypatch, lambda ops: [])
    assert asyncio.run(GlobalBlacklist().remove_entry("%")) is False
    flat = [op for q in queries for op in q.ops]
    assert ("ilike", ("ingame_name", "\\%")) in flat
    assert ("delete", ()) not in flat

"""Concurrent commands must retain independent persisted configuration changes."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock


class _Store:
    def __init__(self, data):
        self.data = data

    async def load(self):
        snapshot = deepcopy(self.data)
        await asyncio.sleep(0)
        return snapshot

    async def save(self, data):
        await asyncio.sleep(0)
        self.data = deepcopy(data)


def _interaction():
    return SimpleNamespace(
        user=SimpleNamespace(id=7),
        guild=SimpleNamespace(id=123),
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        edit_original_response=mock.AsyncMock(),
    )


def test_tts_independent_name_and_rejoin_edits_survive_overlap(monkeypatch):
    from cogs import alo_tts

    store = _Store({"read_name": {}, "rejoin": {}})
    monkeypatch.setattr(alo_tts, "load_tts_config", store.load)
    monkeypatch.setattr(alo_tts, "save_tts_config", store.save)
    monkeypatch.setattr(alo_tts, "is_officer", lambda user: True)

    async def exercise():
        cog = alo_tts.AloTtsCog(mock.Mock())
        await asyncio.gather(
            cog.alonametoggle_cmd.callback(cog, _interaction()),
            cog.aloconfig_cmd.callback(
                cog, _interaction(), SimpleNamespace(value="on"),
                SimpleNamespace(id=200, name="synthetic voice"),
            ),
        )

    asyncio.run(exercise())
    assert store.data == {"read_name": {"123": False}, "rejoin": {"200": True}}


def test_guild_id_and_region_edits_survive_overlap(monkeypatch):
    from cogs import guildcheck

    store = _Store({"guild_id": "old-guild", "region": "Asia"})
    monkeypatch.setattr(guildcheck, "load_guildcheck_config", store.load)
    monkeypatch.setattr(guildcheck, "save_guildcheck_config", store.save)
    monkeypatch.setattr(guildcheck, "is_officer", lambda user: True)

    async def exercise():
        cog = guildcheck.GuildCheckCog(mock.Mock())
        await asyncio.gather(
            cog.guildconfig_cmd.callback(cog, _interaction(), guild_id="new-guild"),
            cog.guildconfig_cmd.callback(
                cog, _interaction(), region=SimpleNamespace(value="Europe"),
            ),
        )

    asyncio.run(exercise())
    assert store.data == {"guild_id": "new-guild", "region": "Europe"}

"""Finance behavior invariants exercised with isolated integration boundaries."""
import asyncio
from types import SimpleNamespace
from unittest import mock


def test_sp_parser_uses_every_valid_row_and_excludes_bad_late_timestamp():
    from cogs.siphoned import parse_sp_log

    text = (
        '"Date"\t"Player"\t"Reason"\t"Amount"\n'
        '"2026-10-01 12:00:00"\t"A"\t"Deposit"\t"10"\n'
        '"2026-10-03 12:00:00"\t"B"\t"Deposit"\t"not-a-number"\n'
        '"2026-10-02 12:00:00"\t"C"\t"Withdrawal"\t"-4"\n'
    )
    rows, invalid = parse_sp_log(text)

    assert [row["player_name"] for row in rows] == ["A", "C"]
    assert [row["log_timestamp"] for row in rows] == [
        "2026-10-01 12:00:00",
        "2026-10-02 12:00:00",
    ]
    assert max(row["log_timestamp"] for row in rows) == "2026-10-02 12:00:00"
    assert invalid == 1


def test_core_unknown_bank_result_is_claimed_once_and_not_retried(monkeypatch):
    from cogs import corebank

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def __init__(self):
            self.patch_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def patch(self, url, *, headers, json):
            self.patch_count += 1
            self.last_patch = (url, headers, json)
            return FakeResponse(504)

    session = FakeSession()
    monkeypatch.setattr(corebank.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setattr(corebank, "is_officer", lambda member: True)
    cog = corebank.CoreBankCog(mock.Mock())
    cog.config = {
        "core_channel_id": "100",
        "bank_channel_id": "200",
        "unbelievaboat_token": "test-token",
        "emoji_map": {"green": {"name": "Green", "value": 100, "display": "🟢"}},
    }
    recipient = SimpleNamespace(id=456, bot=False, mention="<@456>")
    officer = SimpleNamespace(id=789, mention="<@789>")
    message = SimpleNamespace(author=recipient, content="proof", id=300)
    channel = mock.Mock()
    channel.fetch_message = mock.AsyncMock(return_value=message)
    channel.send = mock.AsyncMock()
    guild = mock.Mock()
    guild.get_channel.return_value = mock.Mock()
    cog._reaction_context = mock.AsyncMock(return_value=(guild, channel, officer))

    ledger = {"status": "new"}
    claims = []
    transitions = []

    async def rpc(name, params):
        if name != "claim_core_credit":
            raise AssertionError(f"Unexpected RPC: {name}")
        claims.append(params)
        if ledger["status"] != "new":
            return {"claimed": False, "entry": None}
        ledger["status"] = "pending"
        return {
            "claimed": True,
            "entry": {
                "amount": params["p_amount"],
                "recipient_id": params["p_recipient_id"],
                "guild_id": params["p_guild_id"],
                "core_name": params["p_core_name"],
                "core_display": params["p_core_display"],
            },
        }

    async def transition(message_id, expected, next_status):
        transitions.append((message_id, expected, next_status))
        if ledger["status"] != expected:
            return False
        ledger["status"] = next_status
        return True

    cog._call_rpc = rpc
    cog._transition = transition
    payload = SimpleNamespace(
        user_id=officer.id,
        guild_id=123,
        channel_id=100,
        message_id=300,
        emoji=SimpleNamespace(id=None, name="green"),
    )

    async def exercise():
        await cog.on_raw_reaction_add(payload)
        await cog.on_raw_reaction_add(payload)

    asyncio.run(exercise())

    assert session.patch_count == 1
    assert ledger["status"] == "unknown"
    assert transitions == [("300:green", "pending", "unknown")]
    assert claims[0]["p_recipient_id"] == "456"
    assert claims[0]["p_amount"] == 100
    assert claims[0]["p_officer_id"] == "789"


def test_refund_uses_credited_ledger_snapshot_after_emoji_removed(monkeypatch):
    from cogs import corebank

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def __init__(self):
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def patch(self, url, *, headers, json):
            self.calls.append((url, headers, json))
            return FakeResponse()

    session = FakeSession()
    monkeypatch.setattr(corebank.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setattr(corebank, "is_officer", lambda member: True)
    entry = {
        "message_id": "300:green",
        "user_id": "789",
        "guild_id": "123",
        "recipient_id": "456",
        "amount": 100,
        "emoji_key": "green",
        "core_name": "Green Core at time of claim",
        "core_display": "🟢",
        "status": "credited",
    }
    monkeypatch.setattr(
        corebank,
        "async_execute",
        mock.AsyncMock(return_value=(SimpleNamespace(data=[entry]), None)),
    )
    cog = corebank.CoreBankCog(mock.Mock())
    cog.config = {"core_channel_id": "100", "unbelievaboat_token": "test-token", "emoji_map": {}}
    recipient = SimpleNamespace(id=456, mention="<@456>")
    officer = SimpleNamespace(id=789, mention="<@789>")
    message = SimpleNamespace(author=recipient, content="proof")
    channel = mock.Mock()
    channel.fetch_message = mock.AsyncMock(return_value=message)
    channel.send = mock.AsyncMock()
    guild = mock.Mock()
    guild.get_member.return_value = recipient
    cog._reaction_context = mock.AsyncMock(return_value=(guild, channel, officer))
    transitions = []

    async def transition(message_id, expected, next_status):
        transitions.append((message_id, expected, next_status))
        return True

    cog._transition = transition
    payload = SimpleNamespace(
        user_id=officer.id,
        guild_id=123,
        channel_id=100,
        message_id=300,
        emoji=SimpleNamespace(id=None, name="green"),
    )
    asyncio.run(cog.on_raw_reaction_remove(payload))

    assert session.calls[0][0].endswith("/guilds/123/users/456")
    assert session.calls[0][2]["bank"] == -100
    assert "Green Core at time of claim" in session.calls[0][2]["reason"]
    assert transitions == [
        ("300:green", "credited", "reverting"),
        ("300:green", "reverting", "reverted"),
    ]
    assert channel.send.await_count == 1


def test_split_attachment_failure_keeps_original_message():
    from cogs.corebank import CoreBankCog

    cog = CoreBankCog(mock.Mock())
    cog.config = {"core_channel_id": "100", "auto_react": True, "emoji_map": {}}
    first = mock.Mock()
    first.to_file = mock.AsyncMock(return_value="reposted-file")
    second = mock.Mock()
    second.to_file = mock.AsyncMock(side_effect=OSError("download failed"))
    channel = mock.Mock(id=100, parent_id=None)
    channel.send = mock.AsyncMock()
    message = SimpleNamespace(
        author=SimpleNamespace(bot=False, mention="<@42>"),
        channel=channel,
        attachments=[first, second],
        content="proof note",
        reply=mock.AsyncMock(),
        delete=mock.AsyncMock(),
    )

    asyncio.run(cog.on_message(message))

    assert channel.send.await_count == 1
    message.delete.assert_not_awaited()


def test_core_config_reload_refreshes_real_cached_values(monkeypatch):
    from cogs import corebank

    monkeypatch.setattr(corebank, "GUILD_ID", "123")
    config = {
        "guild_id": "123",
        "core_channel_id": "A",
        "bank_channel_id": "bank-a",
        "emoji_map": {"x": {"name": "X", "value": 10, "display": "x"}},
    }
    from copy import deepcopy
    from core import config_store

    monkeypatch.setattr(config_store, "_cache", {})
    monkeypatch.setattr(config_store, "safe_select", lambda *args, **kwargs: (deepcopy(config), None))
    cog = corebank.CoreBankCog(mock.Mock())

    async def exercise():
        await cog.cog_load()
        config.update({"core_channel_id": "B", "bank_channel_id": "bank-b", "emoji_map": {}})
        await cog.on_config_reload()

    asyncio.run(exercise())

    assert cog.config["core_channel_id"] == "B"
    assert cog.config["bank_channel_id"] == "bank-b"
    assert cog.config["emoji_map"] == {}


def test_core_credit_without_token_never_claims_or_calls_provider(monkeypatch):
    from cogs import corebank

    monkeypatch.setattr(corebank, "is_officer", lambda member: True)
    provider_session = mock.Mock()
    monkeypatch.setattr(corebank.aiohttp, "ClientSession", provider_session)
    cog = corebank.CoreBankCog(mock.Mock())
    cog.config = {
        "core_channel_id": "100",
        "bank_channel_id": "200",
        "unbelievaboat_token": "",
        "emoji_map": {"green": {"name": "Green", "value": 10, "display": "🟢"}},
    }
    officer = SimpleNamespace(id=7)
    channel = mock.Mock()
    channel.fetch_message = mock.AsyncMock(
        return_value=SimpleNamespace(author=SimpleNamespace(id=456, bot=False), content="proof")
    )
    channel.send = mock.AsyncMock()
    cog._reaction_context = mock.AsyncMock(return_value=(mock.Mock(), channel, officer))
    cog._call_rpc = mock.AsyncMock()
    payload = SimpleNamespace(
        user_id=7,
        guild_id=123,
        channel_id=100,
        message_id=300,
        emoji=SimpleNamespace(id=None, name="green"),
    )

    asyncio.run(cog.on_raw_reaction_add(payload))

    cog._call_rpc.assert_not_awaited()
    provider_session.assert_not_called()


def test_core_setup_acknowledges_before_config_persistence(monkeypatch):
    from cogs import corebank

    monkeypatch.setattr(corebank, "is_officer", lambda member: True)
    events = []
    cog = corebank.CoreBankCog(mock.Mock())

    async def patch_config(patch):
        events.append("persist")
        return True

    cog._patch_config = patch_config
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=7),
        response=SimpleNamespace(
            defer=mock.AsyncMock(side_effect=lambda **kwargs: events.append("defer"))
        ),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )
    core_channel = SimpleNamespace(id=100, mention="#core")
    bank_channel = SimpleNamespace(id=200, mention="#bank")

    asyncio.run(
        cog.coresetup_cmd.callback(
            cog, interaction, core_channel, bank_channel, "test-token"
        )
    )

    assert events == ["defer", "persist"]


def test_sp_update_acknowledges_before_download_and_atomic_import(monkeypatch):
    from cogs import siphoned

    events = []

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        async def text(self, *, encoding, errors):
            return '"2026-10-01 12:00:00"\t"Ada"\t"Deposit"\t"10"'

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, url):
            events.append("download")
            return FakeResponse()

    async def import_rows(rows):
        events.append("commit")
        assert rows == [{
            "player_name": "Ada",
            "amount": 10,
            "log_timestamp": "2026-10-01 12:00:00",
        }]
        return {"applied": 1, "skipped": 0, "last_update": "2026-10-01 12:00:00"}

    async def followup(*args, **kwargs):
        events.append("followup")

    monkeypatch.setattr(siphoned.aiohttp, "ClientSession", FakeSession)
    monkeypatch.setattr(siphoned, "apply_sp_import", import_rows)
    cog = siphoned.SiphonedCog(mock.Mock())
    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock(side_effect=lambda: events.append("defer"))),
        followup=SimpleNamespace(send=mock.AsyncMock(side_effect=followup)),
    )

    asyncio.run(
        cog.spupdate.callback(
            cog,
            interaction,
            SimpleNamespace(filename="siphoned.txt", url="https://example.invalid/log"),
        )
    )

    assert events == ["defer", "download", "commit", "followup"]


def test_core_unavailable_config_does_not_masquerade_as_empty_then_recovers(monkeypatch):
    from copy import deepcopy
    from core import config_store
    from cogs import corebank

    available = False
    row = {
        "guild_id": "123", "core_channel_id": "100", "bank_channel_id": "200",
        "unbelievaboat_token": "synthetic-secret",
        "emoji_map": {"green": {"name": "Green", "value": 100, "display": "G"}},
    }

    def select(*args, **kwargs):
        return (deepcopy(row), None) if available else (None, "synthetic timeout")

    monkeypatch.setattr(corebank, "GUILD_ID", "123")
    monkeypatch.setattr(config_store, "_cache", {})
    monkeypatch.setattr(config_store, "safe_select", select)

    async def exercise():
        nonlocal available
        cog = corebank.CoreBankCog(mock.Mock())
        await cog.cog_load()
        interaction = SimpleNamespace(response=SimpleNamespace(send_message=mock.AsyncMock()))
        await cog.corelist_cmd.callback(cog, interaction)
        unavailable = interaction.response.send_message.await_args
        assert not cog.config_loaded
        assert "embed" not in unavailable.kwargs

        available = True
        await cog.on_config_reload()
        await cog.corelist_cmd.callback(cog, interaction)
        recovered = interaction.response.send_message.await_args
        assert cog.config_loaded
        assert "embed" in recovered.kwargs
        assert cog.config["core_channel_id"] == "100"
        assert cog.config["emoji_map"]["green"]["value"] == 100

    asyncio.run(exercise())

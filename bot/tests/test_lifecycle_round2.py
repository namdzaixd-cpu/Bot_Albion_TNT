"""Regression round 2: view lifecycle, onboarding approval, guild strip retry, embed budgets."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import discord
from discord.ext import commands

import cogs.guildcheck as guildcheck
import cogs.massing as massing
import cogs.onboarding as onboarding_module
from cogs.onboarding import OfficerApprovalView, Onboarding, application_marker


def _real_bot():
    return commands.Bot(command_prefix="!", intents=discord.Intents.none())


def _party(roles, weapon_slots, **extra):
    party = {
        "id": "9001",
        "name": "P" * 300,
        "time": "T" * 2000,
        "roles": roles,
        "weapon_slots": weapon_slots,
        "slots": {r: {} for r in roles},
        "fills": [],
        "note": "N" * 3000,
        "creator": 1,
        "creator_name": "C" * 3000,
    }
    party.update(extra)
    return party


def _assert_embed_valid(embed):
    assert len(embed) <= 6000
    assert len(embed.title or "") <= 256
    for field in embed.fields:
        assert len(field.name) <= 256
        assert len(field.value) <= 1024
    assert len(embed.fields) <= 25


# ------------------------------------------------------------------ massing


def test_real_bot_add_view_accepts_party_with_more_than_12_slots():
    async def run():
        roles = [f"R{i}" for i in range(14)]
        party = _party(roles, {r: [(r, 1)] for r in roles})
        bot = _real_bot()
        with mock.patch.dict(massing.active_parties, {party["id"]: party}, clear=True):
            view = massing.PartyView(party["id"])
            assert any(isinstance(c, massing.PartySlotSelect) for c in view.children)
            assert view.is_persistent()
            bot.add_view(view)  # discord.py ném ValueError nếu có item thiếu custom_id
            assert view in bot.persistent_views

    asyncio.run(run())


def test_party_embed_stays_valid_with_many_members_and_keeps_state():
    roles = ["DPS", "Healer"] + [f"X{i}" for i in range(13)]
    wslots = {"DPS": [("DPS", 47)], "Healer": [("Bow", 5), ("Sword", 5)]}
    wslots.update({f"X{i}": [(f"X{i}", 47)] for i in range(13)})
    party = _party(roles, wslots)
    uid = 100000000000000000
    for role in roles:
        for weapon, limit in wslots[role]:
            party["slots"][role][weapon] = list(range(uid, uid + limit))
            uid += limit
    party["fills"] = list(range(uid, uid + 80))
    snapshot = deepcopy(party)

    embed = massing.build_party_embed(party)

    _assert_embed_valid(embed)
    assert party == snapshot  # render không làm mất state
    fill_field = next(f for f in embed.fields if f.name.startswith("🔄 Fill"))
    assert "…+" in fill_field.value  # phần dư được báo thay vì làm Discord từ chối embed


def test_party_embed_single_large_slot_renders_all_it_can_within_field():
    party = _party(["DPS"], {"DPS": [("DPS", 47)]}, name="ok", time="ok", note="")
    party["slots"]["DPS"]["DPS"] = list(range(100000000000000000, 100000000000000047))
    embed = massing.build_party_embed(party)
    _assert_embed_valid(embed)
    dps = next(f for f in embed.fields if "DPS" in f.name)
    assert "<@100000000000000000>" in dps.value


def test_ping_all_splits_messages_under_discord_limit_and_validates_input():
    async def run():
        members = list(range(100000000000000000, 100000000000000300))
        modal = massing.PingAllModal(members)
        sent = []
        interaction = mock.Mock()
        interaction.response.send_message = mock.AsyncMock(side_effect=lambda c, **k: sent.append(c))
        interaction.followup.send = mock.AsyncMock(side_effect=lambda c, **k: sent.append(c))
        with mock.patch.object(type(modal.ping_message), "value", new_callable=mock.PropertyMock, return_value="x" * 300):
            await modal.on_submit(interaction)
        assert len(sent) > 1 and all(len(m) <= 2000 for m in sent)
        text = "\n".join(sent)
        assert all(f"<@{m}>" in text for m in members)

        empty_interaction = mock.Mock()
        empty_interaction.response.send_message = mock.AsyncMock()
        empty_interaction.followup.send = mock.AsyncMock()
        with mock.patch.object(type(modal.ping_message), "value", new_callable=mock.PropertyMock, return_value="   "):
            await modal.on_submit(empty_interaction)
        assert empty_interaction.response.send_message.await_args.kwargs.get("ephemeral") is True
        empty_interaction.followup.send.assert_not_awaited()

    asyncio.run(run())


# --------------------------------------------------------------- onboarding


def _forum_with_threads():
    def make_thread(thread_id, message_id, title, footer):
        thread = mock.Mock(id=thread_id, guild=mock.Mock(id=123))
        embed = discord.Embed(title=title)
        embed.url = application_marker(thread)
        embed.set_footer(text=footer)
        report = mock.Mock(id=message_id, embeds=[embed])

        async def history(limit=None):
            yield report

        thread.history = history
        return thread

    active = make_thread(1, 701, "⏳ Chờ duyệt: A", "YOB: 2005 | Submitted")
    archived = make_thread(2, 702, "✅ Đã duyệt: B", "YOB: 2005 | Approved | Nickname đã đổi")

    class FakeForum:
        threads = [active]

        async def archived_threads(self, limit=None):
            yield archived

    return FakeForum


def _onboarding_cog(bot):
    cog = Onboarding(bot)
    cog.config.data = {"apply_channel_id": "456"}
    cog.config.load = mock.AsyncMock(return_value=cog.config.data)
    return cog


def test_cache_empty_startup_restores_approval_views_after_ready():
    async def run():
        FakeForum = _forum_with_threads()
        forum = FakeForum()
        ready = asyncio.Event()
        bot = _real_bot()
        cog = _onboarding_cog(bot)
        with (
            mock.patch.object(onboarding_module.discord, "ForumChannel", FakeForum),
            mock.patch.object(bot, "get_channel", side_effect=lambda _id: forum if ready.is_set() else None),
            mock.patch.object(bot, "wait_until_ready", new=ready.wait),
        ):
            await asyncio.wait_for(cog.cog_load(), 1)  # setup_hook không bị chặn bởi wait_until_ready
            await asyncio.sleep(0)
            assert not cog._restore_task.done()
            assert not [v for v in bot.persistent_views if isinstance(v, OfficerApprovalView)]

            ready.set()
            await asyncio.wait_for(cog._restore_task, 1)

        views = {v.status: v for v in bot.persistent_views if isinstance(v, OfficerApprovalView)}
        assert set(views) == {"submitted", "approved"}  # thread active + archived
        assert not views["submitted"].renamed and views["approved"].renamed
        assert cog.application_states == {701: "submitted", 702: "approved"}
        assert cog.renamed_applications == {702}
        # chỉ view theo message, không có view global
        assert set(bot._connection._view_store._synced_message_views) == {701, 702}

    asyncio.run(run())


def test_unload_cancels_pending_restoration_task():
    async def run():
        bot = _real_bot()
        cog = _onboarding_cog(bot)
        with mock.patch.object(bot, "wait_until_ready", new=asyncio.Event().wait):
            await cog.cog_load()
            task = cog._restore_task
            await asyncio.sleep(0)
            await cog.cog_unload()
        assert task.cancelled()

    asyncio.run(run())


def _approve_interaction(member, role):
    embed = discord.Embed(title="⏳ Chờ duyệt: Player")
    embed.set_footer(text="User: 555 | YOB: 2000")
    guild = mock.Mock()
    guild.me = mock.Mock(id=1)
    guild.get_member.return_value = member
    guild.get_role.return_value = role
    interaction = mock.Mock()
    interaction.guild = guild
    interaction.user = mock.Mock(id=9, display_name="Officer")
    interaction.client.user.id = 1
    interaction.message = mock.Mock(id=900, embeds=[embed], content="")
    interaction.message.edit = mock.AsyncMock()
    interaction.channel.send = mock.AsyncMock()
    interaction.response.defer = mock.AsyncMock()
    interaction.followup.send = mock.AsyncMock()
    return interaction


def _approve(cog, interaction):
    view = OfficerApprovalView(cog)
    with (
        mock.patch.object(onboarding_module, "check_officer_permission", return_value=True),
        mock.patch.object(onboarding_module, "load_guildcheck_config", new=mock.AsyncMock(return_value={})),
    ):
        return OfficerApprovalView.approve(view, interaction, None)


def test_approve_role_grant_failure_stays_submitted_and_is_retryable():
    async def run():
        cog = Onboarding(mock.Mock())
        cog.config.data = {"member_role_id": "77"}
        member = mock.Mock(id=555)
        member.add_roles = mock.AsyncMock(side_effect=[discord.Forbidden(mock.Mock(status=403, reason="x"), "no"), None])
        interaction = _approve_interaction(member, mock.Mock())

        await _approve(cog, interaction)
        assert cog.application_states.get(900) in (None, "submitted")
        interaction.message.edit.assert_not_awaited()
        interaction.channel.send.assert_not_awaited()  # không welcome giả

        await _approve(cog, interaction)  # retry sau khi sửa quyền
        assert cog.application_states[900] == "approved"
        interaction.message.edit.assert_awaited()
        interaction.channel.send.assert_awaited()

    asyncio.run(run())


def test_approve_missing_role_config_stays_submitted():
    async def run():
        for data, role in (({}, None), ({"member_role_id": "77"}, None)):
            cog = Onboarding(mock.Mock())
            cog.config.data = data
            member = mock.Mock(id=555)
            member.add_roles = mock.AsyncMock()
            interaction = _approve_interaction(member, role)
            await _approve(cog, interaction)
            assert cog.application_states.get(900) in (None, "submitted")
            member.add_roles.assert_not_awaited()
            interaction.channel.send.assert_not_awaited()

    asyncio.run(run())


def test_approve_transient_member_lookup_error_stays_submitted():
    async def run():
        cog = Onboarding(mock.Mock())
        cog.config.data = {"member_role_id": "77"}
        interaction = _approve_interaction(None, mock.Mock())
        interaction.guild.fetch_member = mock.AsyncMock(side_effect=RuntimeError("503"))
        await _approve(cog, interaction)
        assert cog.application_states.get(900) in (None, "submitted")
        interaction.message.edit.assert_not_awaited()

    asyncio.run(run())


# --------------------------------------------------------------- guildcheck


class FakeRole:
    def __init__(self, role_id, position, name):
        self.id, self.position, self.name, self.managed = role_id, position, name, False

    def __lt__(self, other):
        return self.position < other.position


def _strip_fixture():
    everyone, member_role, bot_top = FakeRole(1, 0, "@everyone"), FakeRole(2, 1, "Member"), FakeRole(9, 50, "Bot")
    member = mock.Mock()
    member.roles = [everyone, member_role]
    member.mention = "<@555>"
    guild = mock.Mock()
    guild.default_role = everyone
    guild.me.top_role = bot_top
    guild.get_member.return_value = member
    guild.get_role.return_value = None
    return guild, member


def _registry_row(discord_id="555"):
    return mock.AsyncMock(return_value=(SimpleNamespace(data={"discord_id": discord_id}), None))


def test_failed_strip_preserves_registry_and_snapshot_then_retry_succeeds():
    async def run():
        guild, member = _strip_fixture()
        member.remove_roles = mock.AsyncMock(side_effect=[discord.HTTPException(mock.Mock(status=500, reason="x"), "boom"), None])
        delete = mock.AsyncMock(return_value=None)
        bot = mock.Mock()
        bot.get_guild.return_value = guild
        cog = guildcheck.GuildCheckCog(bot)
        cog._missing_counts["p2"] = 2
        config = {"guild_id": "g1", "region": "Asia", "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""}
        store = {"guild_id": "g1", "region": "Asia", "updated_at": "x", "members": {"p1": "One", "p2": "Two"}}

        async def save(data):
            store.update(data)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=[{"Id": "p1", "Name": "One"}])),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(side_effect=lambda: dict(store))),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock(side_effect=save)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value={"GuildId": "other", "GuildName": "O"})),
            mock.patch.object(guildcheck, "albion_search_player", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(guildcheck, "async_execute", new=_registry_row()),
            mock.patch.object(guildcheck, "registry_delete", new=delete),
            mock.patch.object(guildcheck.asyncio, "sleep", new=mock.AsyncMock()),
            mock.patch.object(cog, "_send_log", new=mock.AsyncMock()),
        ):
            await cog._run_leave_watcher()
            delete.assert_not_awaited()  # registry còn nguyên
            assert "p2" in store["members"]  # snapshot giữ để thử lại

            await cog._run_leave_watcher()  # chu kỳ sau: remove_roles thành công
            delete.assert_awaited_once_with("555")
            assert "p2" not in store["members"]

    asyncio.run(run())


def test_strip_distinguishes_member_gone_from_transient_fetch_error():
    async def run():
        guild, _ = _strip_fixture()
        guild.get_member.return_value = None
        cog = guildcheck.GuildCheckCog(mock.Mock())
        with mock.patch.object(guildcheck, "async_execute", new=_registry_row()):
            guild.fetch_member = mock.AsyncMock(side_effect=discord.NotFound(mock.Mock(status=404, reason="x"), "gone"))
            assert await cog._strip_roles(guild, "p", "I", "G", "", "") == guildcheck.STRIP_SKIPPED
            guild.fetch_member = mock.AsyncMock(side_effect=RuntimeError("503"))
            assert await cog._strip_roles(guild, "p", "I", "G", "", "") == guildcheck.STRIP_RETRY
        with mock.patch.object(guildcheck, "async_execute", new=mock.AsyncMock(return_value=(None, "db down"))):
            assert await cog._strip_roles(guild, "p", "I", "G", "", "") == guildcheck.STRIP_RETRY

    asyncio.run(run())


def _forcestrip_interaction():
    interaction = mock.Mock()
    interaction.user = mock.Mock(display_name="Officer")
    interaction.guild = mock.Mock()
    interaction.response.defer = mock.AsyncMock()
    interaction.followup.send = mock.AsyncMock()
    return interaction


def _run_forcestrip(rows, outcomes):
    async def run():
        cog = guildcheck.GuildCheckCog(mock.Mock())
        interaction = _forcestrip_interaction()
        saved = {}

        async def save(data):
            saved.update(data)

        config = {"guild_id": "g1", "region": "Asia", "guest_role_id": "", "log_channel_id": ""}
        with (
            mock.patch.object(guildcheck, "is_officer", return_value=True),
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=[{"Id": "keep", "Name": "K"}])),
            mock.patch.object(guildcheck, "registry_get_all", new=mock.AsyncMock(return_value=rows)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value={"GuildId": "o", "GuildName": "G" * 200})),
            mock.patch.object(guildcheck, "albion_search_player", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock(side_effect=save)),
            mock.patch.object(guildcheck.asyncio, "sleep", new=mock.AsyncMock()),
            mock.patch.object(cog, "_strip_roles", new=mock.AsyncMock(side_effect=outcomes)),
        ):
            await guildcheck.GuildCheckCog.forcestrip_cmd.callback(cog, interaction)
        return interaction.followup.send.await_args.kwargs["embed"], saved

    return asyncio.run(run())


def test_forcestrip_reports_only_real_successes_and_keeps_retry_in_snapshot():
    rows = [
        {"player_id": "ok", "ign": "Good", "discord_id": "1"},
        {"player_id": "bad", "ign": "Failed", "discord_id": "2"},
        {"player_id": "skip", "ign": "Unlinked", "discord_id": "3"},
    ]
    embed, saved = _run_forcestrip(rows, [guildcheck.STRIP_DONE, guildcheck.STRIP_RETRY, guildcheck.STRIP_SKIPPED])
    fields = {f.name: f.value for f in embed.fields}
    processed = fields["🗑️ Danh sách đã xử lý"]
    assert "Good" in processed and "Failed" not in processed and "Unlinked" not in processed
    assert "`1`" in fields["🚨 Đã gỡ role (out guild)"]
    assert "Failed" in next(v for k, v in fields.items() if k.startswith("⚠️ Gỡ role thất bại"))
    assert saved["members"] == {"keep": "K", "bad": "Failed"}


def test_forcestrip_report_stays_valid_for_huge_purge_and_giant_names():
    rows = [{"player_id": f"p{i}", "ign": "I" * 500, "discord_id": str(100000000000000000 + i)} for i in range(120)]
    embed, _ = _run_forcestrip(rows, [guildcheck.STRIP_DONE] * 120)
    _assert_embed_valid(embed)
    assert "người khác" in next(f.value for f in embed.fields if f.name.startswith("🗑️"))


def test_registerlist_pages_fit_budget_with_max_ign_and_junk_ids():
    rows = [
        {
            "discord_id": str(100000000000000000 + i) if i % 7 else "x" * 400,
            "ign": "M" * 200,
            "region": "Asia" * 10,
            "registered_by": "9" * 19 if i % 2 else "y" * 400,
        }
        for i in range(200)
    ]
    view = guildcheck.RegisterListPaginationView(author=mock.Mock(), rows=rows)
    seen = 0
    for page in range(view.total_pages):
        view.current_page = page
        embed = view.get_embed()
        _assert_embed_valid(embed)
        seen += embed.fields[0].value.count("`#")
    assert seen == 200  # mọi dòng đều xuất hiện đúng một lần qua các trang
    assert view.total_pages > 200 // 15  # số trang theo ký tự, không theo số dòng cố định

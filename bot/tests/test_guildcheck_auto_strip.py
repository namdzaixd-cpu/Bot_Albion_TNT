"""
Tests cho GuildCheck Registry & Auto-Strip tính năng:
- Tự động gỡ role khi thành viên rời guild in-game
- /registertnc, /unregistertnc, /registerlist
"""
import asyncio
from unittest import mock

import cogs.guildcheck as guildcheck


# ==============================================================================
# TEST REGISTRY HELPERS (không gọi DB thật — mock async_execute)
# ==============================================================================

def test_registry_upsert_calls_supabase():
    async def run():
        with mock.patch.object(guildcheck, "async_execute", new=mock.AsyncMock(return_value=(None, None))) as mocked:
            err = await guildcheck.registry_upsert("111", "pid1", "TestIGN", "Asia", "222")
            assert err is None
            mocked.assert_awaited_once()
    asyncio.run(run())


def test_registry_delete_calls_supabase():
    async def run():
        with mock.patch.object(guildcheck, "async_execute", new=mock.AsyncMock(return_value=(None, None))) as mocked:
            err = await guildcheck.registry_delete("111")
            assert err is None
            mocked.assert_awaited_once()
    asyncio.run(run())


def test_registry_get_returns_none_when_no_row():
    async def run():
        fake_res = mock.Mock()
        fake_res.data = None
        with mock.patch.object(guildcheck, "async_execute", new=mock.AsyncMock(return_value=(fake_res, None))):
            result = await guildcheck.registry_get("999")
            assert result is None
    asyncio.run(run())


def test_registry_get_all_returns_empty_on_error():
    async def run():
        with mock.patch.object(guildcheck, "async_execute", new=mock.AsyncMock(return_value=(None, "err"))):
            result = await guildcheck.registry_get_all()
            assert result == []
    asyncio.run(run())


# ==============================================================================
# TEST WATCHER LOGIC — baseline, circuit breaker, double-check
# ==============================================================================

def _make_cog():
    bot = mock.Mock()
    bot.get_guild = mock.Mock(return_value=None)
    cog = guildcheck.GuildCheckCog(bot)
    return cog


def test_watcher_skips_when_auto_strip_disabled():
    async def run():
        cog = _make_cog()
        config = {"guild_id": "g1", "region": "Asia", "auto_strip_enabled": False}
        with mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)):
            await cog._run_leave_watcher()
            # Không gọi API Albion khi auto_strip = False
    asyncio.run(run())


def test_watcher_saves_baseline_on_first_run():
    async def run():
        cog = _make_cog()
        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        members_raw = [
            {"Id": "p1", "Name": "Player1"},
            {"Id": "p2", "Name": "Player2"},
        ]
        empty_snapshot = {"guild_id": "", "region": "", "updated_at": "", "members": {}}

        guild_mock = mock.Mock()
        guild_mock.me.top_role.position = 10
        cog.bot.get_guild = mock.Mock(return_value=guild_mock)

        saved = {}

        async def fake_save(data):
            saved.update(data)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=members_raw)),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(return_value=empty_snapshot)),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock(side_effect=fake_save)),
        ):
            await cog._run_leave_watcher()
            # Lần đầu: lưu baseline với 2 member, không gỡ role ai
            assert saved.get("guild_id") == "g1"
            assert "p1" in saved.get("members", {})
            assert "p2" in saved.get("members", {})
    asyncio.run(run())


def test_watcher_circuit_breaker_blocks_mass_removal():
    async def run():
        cog = _make_cog()
        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        # Snapshot cũ: 20 người, hiện tại chỉ còn 5 → 15 biến mất (>30%)
        prev = {f"p{i}": f"Player{i}" for i in range(20)}
        curr_raw = [{"Id": f"p{i}", "Name": f"Player{i}"} for i in range(5)]

        snapshot = {"guild_id": "g1", "region": "Asia", "updated_at": "x", "members": prev}

        guild_mock = mock.Mock()
        guild_mock.me.top_role.position = 10
        guild_mock.get_channel = mock.Mock(return_value=None)
        guild_mock.members = []
        cog.bot.get_guild = mock.Mock(return_value=guild_mock)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=curr_raw)),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(return_value=snapshot)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock()) as mock_check,
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock()),
            mock.patch.object(cog, "_send_log", new=mock.AsyncMock()),
        ):
            await cog._run_leave_watcher()
            # Circuit breaker: không gọi double-check, không gỡ role ai
            mock_check.assert_not_awaited()
    asyncio.run(run())


def test_watcher_keeps_member_when_double_check_still_in_guild():
    async def run():
        cog = _make_cog()
        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        # Snapshot cũ: p1 + p2, API danh sách trả thiếu p2 (cache lag)
        prev = {"p1": "Player1", "p2": "Player2"}
        curr_raw = [{"Id": "p1", "Name": "Player1"}]  # p2 bị thiếu
        snapshot = {"guild_id": "g1", "region": "Asia", "updated_at": "x", "members": prev}

        # Double-check: p2 vẫn có GuildId == "g1"
        player_info = {"Id": "p2", "Name": "Player2", "GuildId": "g1"}

        guild_mock = mock.Mock()
        cog.bot.get_guild = mock.Mock(return_value=guild_mock)

        saved = {}

        async def fake_save(data):
            saved.update(data)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=curr_raw)),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(return_value=snapshot)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value=player_info)),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock(side_effect=fake_save)),
            mock.patch.object(cog, "_strip_roles", new=mock.AsyncMock()) as mock_strip,
        ):
            await cog._run_leave_watcher()
            # p2 vẫn còn trong guild → không gỡ role
            mock_strip.assert_not_awaited()
            # p2 được giữ lại trong snapshot
            assert "p2" in saved.get("members", {})
    asyncio.run(run())


def test_watcher_strips_roles_when_confirmed_left():
    async def run():
        cog = _make_cog()
        # Đặt bộ đếm vắng mặt = 2 để lần này là lần thứ 3 (đủ ngưỡng)
        cog._missing_counts["p2"] = 2

        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        prev = {"p1": "Player1", "p2": "Player2"}
        curr_raw = [{"Id": "p1", "Name": "Player1"}]
        snapshot = {"guild_id": "g1", "region": "Asia", "updated_at": "x", "members": prev}

        # Double-check: p2 đã rời guild (GuildId khác)
        player_info = {"Id": "p2", "Name": "Player2", "GuildId": "other-guild", "GuildName": "OtherGuild"}

        guild_mock = mock.Mock()
        cog.bot.get_guild = mock.Mock(return_value=guild_mock)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=curr_raw)),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(return_value=snapshot)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value=player_info)),
            mock.patch.object(guildcheck, "albion_search_player", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock()),
            mock.patch.object(cog, "_strip_roles", new=mock.AsyncMock()) as mock_strip,
        ):
            await cog._run_leave_watcher()
            # p2 đã rời guild và đủ 3 lần vắng mặt → gọi _strip_roles
            mock_strip.assert_awaited_once()
            call_args = mock_strip.call_args
            assert call_args.args[2] == "Player2"  # ign
    asyncio.run(run())


def test_watcher_keeps_member_in_snapshot_when_api_error():
    async def run():
        cog = _make_cog()
        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        prev = {"p1": "Player1", "p2": "Player2"}
        curr_raw = [{"Id": "p1", "Name": "Player1"}]
        snapshot = {"guild_id": "g1", "region": "Asia", "updated_at": "x", "members": prev}

        guild_mock = mock.Mock()
        cog.bot.get_guild = mock.Mock(return_value=guild_mock)

        saved = {}

        async def fake_save(data):
            saved.update(data)

        with (
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=curr_raw)),
            mock.patch.object(guildcheck, "load_guildcheck_snapshot", new=mock.AsyncMock(return_value=snapshot)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value=None)),  # API lỗi
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock(side_effect=fake_save)),
            mock.patch.object(cog, "_strip_roles", new=mock.AsyncMock()) as mock_strip,
        ):
            await cog._run_leave_watcher()
            # API lỗi → giữ lại p2 trong snapshot, không gỡ role
            mock_strip.assert_not_awaited()
            assert "p2" in saved.get("members", {})
    asyncio.run(run())


def test_forcestrip_cmd_strips_out_guild_member():
    async def run():
        cog = _make_cog()
        config = {
            "guild_id": "g1", "region": "Asia",
            "auto_strip_enabled": True, "log_channel_id": "", "guest_role_id": ""
        }
        # In-game chỉ còn p1
        curr_raw = [{"Id": "p1", "Name": "Player1"}]
        # Database có cả p1 và p2
        registered = [
            {"discord_id": "101", "player_id": "p1", "ign": "Player1"},
            {"discord_id": "102", "player_id": "p2", "ign": "Player2"},
        ]
        # p2 double-check ra đã out sang guild khác
        p2_info = {"Id": "p2", "Name": "Player2", "GuildId": "other-guild", "GuildName": "Other"}

        interaction = mock.Mock()
        interaction.user = mock.Mock()
        interaction.user.display_name = "OfficerTest"
        interaction.guild = mock.Mock()
        interaction.response = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup = mock.Mock()
        interaction.followup.send = mock.AsyncMock()

        with (
            mock.patch.object(guildcheck, "is_officer", return_value=True),
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(return_value=config)),
            mock.patch.object(guildcheck, "albion_get_guild_members", new=mock.AsyncMock(return_value=curr_raw)),
            mock.patch.object(guildcheck, "registry_get_all", new=mock.AsyncMock(return_value=registered)),
            mock.patch.object(guildcheck, "albion_get_player_by_id", new=mock.AsyncMock(return_value=p2_info)),
            mock.patch.object(guildcheck, "albion_search_player", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(guildcheck, "save_guildcheck_snapshot", new=mock.AsyncMock()),
            mock.patch.object(cog, "_strip_roles", new=mock.AsyncMock()) as mock_strip,
        ):
            await cog.forcestrip_cmd.callback(cog, interaction)
            # p2 phải bị strip
            mock_strip.assert_awaited_once()
            call_args = mock_strip.call_args
            assert call_args.args[1] == "p2"
            assert call_args.args[2] == "Player2"
            # Kiểm tra embed báo cáo gửi ra
            interaction.followup.send.assert_awaited_once()
    asyncio.run(run())

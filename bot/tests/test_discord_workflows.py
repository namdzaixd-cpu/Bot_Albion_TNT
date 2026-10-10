import asyncio
from copy import deepcopy
from unittest import mock

import cogs.alo_tts as alo_tts
import cogs.lastseen as lastseen
import cogs.massing as massing
import cogs.guildcheck as guildcheck
import cogs.update_translator as update_translator


def _party():
    return {
        "id": "party-1",
        "name": "Party",
        "time": "Tonight",
        "creator": 9,
        "roles": ["Healer"],
        "weapon_slots": {"Healer": [("Bow", 1), ("Sword", 1)]},
        "slots": {"Healer": {"Bow": [101], "Sword": [202]}},
        "fills": [],
        "note": "",
    }

def test_massing_failed_restore_preserves_state_and_blocks_overwrite():
    async def run():
        saved_party = _party()
        bot = mock.Mock()
        cog = massing.MassingCog(bot)
        with (
            mock.patch.dict(massing.active_parties, {saved_party["id"]: saved_party}, clear=True),
            mock.patch.dict(massing.active_templates, {}, clear=True),
            mock.patch.object(massing, "_massing_loaded", True),
            mock.patch.object(massing, "_templates_loaded", False),
            mock.patch.object(massing, "load_massing", new=mock.AsyncMock(side_effect=OSError("read failed"))),
            mock.patch.object(massing, "load_templates", new=mock.AsyncMock(return_value={})),
            mock.patch.object(massing.tasks.Loop, "start", lambda self, *args, **kwargs: None),
            mock.patch.object(massing, "save_json_async", new=mock.AsyncMock()) as save_json,
        ):
            await cog.cog_load()
            assert massing.active_parties == {saved_party["id"]: saved_party}
            try:
                await massing.save_massing()
            except RuntimeError:
                pass
            else:
                raise AssertionError("Massing writes must stay locked after load failure")
            save_json.assert_not_awaited()

    asyncio.run(run())
def test_massing_failed_template_restore_preserves_templates_and_blocks_overwrite():
    async def run():
        saved_templates = {"old": {"display_name": "Old"}}
        cog = massing.MassingCog(mock.Mock())
        with (
            mock.patch.dict(massing.active_parties, {}, clear=True),
            mock.patch.dict(massing.active_templates, saved_templates, clear=True),
            mock.patch.object(massing, "_massing_loaded", False),
            mock.patch.object(massing, "_templates_loaded", True),
            mock.patch.object(massing, "load_massing", new=mock.AsyncMock(return_value={})),
            mock.patch.object(massing, "load_templates", new=mock.AsyncMock(side_effect=OSError("read failed"))),
            mock.patch.object(massing.tasks.Loop, "start", lambda self, *args, **kwargs: None),
            mock.patch.object(massing, "save_json_async", new=mock.AsyncMock()) as save_json,
        ):
            await cog.cog_load()
            assert massing.active_templates == saved_templates
            try:
                await massing.save_templates({})
            except RuntimeError:
                pass
            else:
                raise AssertionError("Template writes must stay locked after load failure")
            save_json.assert_not_awaited()

    asyncio.run(run())


def test_massing_layout_accepts_25_components_and_rejects_26():
    roles = ["Healer"]
    weapon_slots = {
        "Healer": [(f"Weapon{i}", 1) for i in range(15)]
    }
    assert massing.validate_party_layout("party-1", roles, weapon_slots) is None

    weapon_slots["Healer"].append(("Weapon15", 1))
    assert massing.validate_party_layout("party-1", roles, weapon_slots) is not None

    long_role = "R" * 90
    assert massing.validate_party_layout(
        "party-1", [long_role], {long_role: [("Sword", 1)]}
    ) is not None


def test_massing_full_capacity_button_label_stays_within_discord_limit():
    assert massing.validate_party_layout("p", ["R"], {"R": [("W" * 70, 100)]}) is None
    assert massing.validate_party_layout("p", ["R"], {"R": [("W" * 71, 100)]}) is not None


def test_massing_join_acknowledges_before_persisting():
    async def run():
        events = []
        party = _party()
        party["slots"]["Healer"] = {"Bow": [], "Sword": []}
        interaction = mock.Mock()
        interaction.user.id = 303
        interaction.response.defer = mock.AsyncMock(side_effect=lambda: events.append("ack"))
        interaction.edit_original_response = mock.AsyncMock()
        with (
            mock.patch.dict(massing.active_parties, {party["id"]: party}, clear=True),
            mock.patch.object(massing, "_massing_loaded", True),
            mock.patch.object(massing, "_massing_state_lock", asyncio.Lock()),
            mock.patch.object(
                massing,
                "save_massing",
                new=mock.AsyncMock(side_effect=lambda previous: events.append("save")),
            ),
        ):
            view = massing.PartyView(party["id"])
            await view.make_join_callback("Healer", "Bow")(interaction)

        assert events == ["ack", "save"]
        assert party["slots"]["Healer"]["Bow"] == [303]

    asyncio.run(run())

def test_massing_failed_save_does_not_rollback_an_overlapping_party_join():
    async def run():
        party_a = _party()
        party_a["slots"]["Healer"]["Bow"] = []
        party_b = deepcopy(party_a)
        party_b["id"] = "party-2"
        first_save_started = asyncio.Event()
        release_first_save = asyncio.Event()
        second_acknowledged = asyncio.Event()
        failed_snapshots = []
        successful_snapshots = []
        save_calls = 0

        async def save_json(data, path):
            nonlocal save_calls
            save_calls += 1
            snapshot = deepcopy(data)
            if save_calls == 1:
                failed_snapshots.append(snapshot)
                first_save_started.set()
                await release_first_save.wait()
                raise OSError("first save failed")
            successful_snapshots.append(snapshot)

        def make_interaction(user_id, ack_event=None):
            interaction = mock.Mock()
            interaction.user.id = user_id
            interaction.response.defer = mock.AsyncMock(
                side_effect=lambda: ack_event.set() if ack_event else None
            )
            interaction.edit_original_response = mock.AsyncMock()
            interaction.followup.send = mock.AsyncMock()
            return interaction

        interaction_a = make_interaction(303)
        interaction_b = make_interaction(404, second_acknowledged)
        with (
            mock.patch.dict(
                massing.active_parties,
                {party_a["id"]: party_a, party_b["id"]: party_b},
                clear=True,
            ),
            mock.patch.object(massing, "_massing_loaded", True),
            mock.patch.object(massing, "_massing_state_lock", asyncio.Lock()),
            mock.patch.object(massing, "save_json_async", new=mock.AsyncMock(side_effect=save_json)),
        ):
            view_a = massing.PartyView(party_a["id"])
            view_b = massing.PartyView(party_b["id"])
            task_a = asyncio.create_task(
                view_a.make_join_callback("Healer", "Bow")(interaction_a)
            )
            await first_save_started.wait()
            task_b = asyncio.create_task(
                view_b.make_join_callback("Healer", "Bow")(interaction_b)
            )
            try:
                await asyncio.wait_for(second_acknowledged.wait(), timeout=1)
            except asyncio.TimeoutError:
                release_first_save.set()
                await asyncio.gather(task_a, task_b, return_exceptions=True)
                raise AssertionError("The second interaction must acknowledge before waiting for the lock")
            await asyncio.sleep(0)
            assert not task_b.done()
            release_first_save.set()
            await asyncio.gather(task_a, task_b)

            assert massing.active_parties[party_a["id"]]["slots"]["Healer"]["Bow"] == []
            assert massing.active_parties[party_b["id"]]["slots"]["Healer"]["Bow"] == [404]
            assert failed_snapshots[0][party_a["id"]]["slots"]["Healer"]["Bow"] == [303]
            assert successful_snapshots[0][party_a["id"]]["slots"]["Healer"]["Bow"] == []
            assert successful_snapshots[0][party_b["id"]]["slots"]["Healer"]["Bow"] == [404]
            interaction_a.followup.send.assert_awaited_once()
            interaction_a.response.defer.assert_awaited_once()
            interaction_b.response.defer.assert_awaited_once()

    asyncio.run(run())

def test_massing_restart_restores_persisted_party_view():
    async def run():
        bot = mock.Mock()
        cog = massing.MassingCog(bot)
        party = _party()
        with (
            mock.patch.dict(massing.active_parties, {}, clear=True),
            mock.patch.dict(massing.active_templates, {}, clear=True),
            mock.patch.object(massing, "_massing_loaded", False),
            mock.patch.object(massing, "_templates_loaded", False),
            mock.patch.object(massing, "load_massing", new=mock.AsyncMock(return_value={party["id"]: party})),
            mock.patch.object(massing, "load_templates", new=mock.AsyncMock(return_value={})),
            mock.patch.object(massing.tasks.Loop, "start", lambda self, *args, **kwargs: None),
        ):
            await cog.cog_load()
            assert massing.active_parties[party["id"]] == party
            bot.add_view.assert_called_once()
            assert isinstance(bot.add_view.call_args.args[0], massing.PartyView)

    asyncio.run(run())
def test_massing_empty_restore_starts_cleanup_after_full_week():
    async def run():
        bot = mock.Mock()
        bot.wait_until_ready = mock.AsyncMock()
        cog = massing.MassingCog(bot)
        starts = []

        def record_start(loop, *args, **kwargs):
            starts.append(loop)

        with (
            mock.patch.dict(massing.active_parties, {}, clear=True),
            mock.patch.dict(massing.active_templates, {}, clear=True),
            mock.patch.object(massing, "_massing_loaded", False),
            mock.patch.object(massing, "_templates_loaded", False),
            mock.patch.object(massing, "load_massing", new=mock.AsyncMock(return_value={})),
            mock.patch.object(massing, "load_templates", new=mock.AsyncMock(return_value={})),
            mock.patch.object(massing.tasks.Loop, "start", record_start),
            mock.patch.object(massing.tasks.Loop, "is_running", lambda loop: False),
        ):
            await cog.cog_load()
            assert len(starts) == 1
            sleep = mock.AsyncMock()
            with mock.patch.object(massing.asyncio, "sleep", new=sleep):
                await cog.before_weekly_clear()
            bot.wait_until_ready.assert_awaited_once()
            sleep.assert_awaited_once_with(168 * 60 * 60)

    asyncio.run(run())



def test_massing_move_to_full_slot_does_not_remove_source_membership():
    async def run():
        party = _party()
        parent_view = mock.Mock()
        parent_view.refresh_original = mock.AsyncMock()
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock()
        interaction.edit_original_response = mock.AsyncMock()
        with (
            mock.patch.dict(massing.active_parties, {party["id"]: party}, clear=True),
            mock.patch.object(massing, "_massing_loaded", True),
            mock.patch.object(massing, "_massing_state_lock", asyncio.Lock()),
            mock.patch.object(massing, "save_massing", new=mock.AsyncMock()) as save,
        ):
            select = massing.SlotPickSelect(party, parent_view, 101, "move")
            select._values = ["Healer|Sword"]
            await select.callback(interaction)

        assert party["slots"]["Healer"]["Bow"] == [101]
        assert party["slots"]["Healer"]["Sword"] == [202]
        parent_view._remove_member_everywhere.assert_not_called()
        save.assert_not_awaited()
        interaction.response.defer.assert_awaited_once()
        interaction.edit_original_response.assert_awaited_once()
        parent_view.refresh_original.assert_awaited_once()

    asyncio.run(run())


def test_lastseen_failed_flush_keeps_dirty_and_unloaded_cache_is_not_saved():
    async def run():
        cog = lastseen.LastSeenCog(mock.Mock())
        cog.cache["1"] = "2026-10-04 12:00:00"
        cog.dirty = True
        db = mock.AsyncMock(side_effect=[(None, "database unavailable"), (mock.Mock(), None)])
        with mock.patch.object(lastseen, "async_execute", new=db):
            assert not await cog.save()
            assert cog.dirty
            db.assert_not_awaited()
            cog.cache_loaded = True
            assert not await cog.save()
            assert cog.dirty
            assert await cog.save()
            assert not cog.dirty
        assert db.await_count == 2

    asyncio.run(run())


def test_lastseen_does_not_clear_dirty_when_new_activity_arrives_during_flush():
    async def run():
        cog = lastseen.LastSeenCog(mock.Mock())
        cog.cache_loaded = True
        cog.cache["1"] = "2026-10-04 12:00:00"
        cog.dirty = True

        async def update_while_saving(*args, **kwargs):
            cog._revision += 1
            return mock.Mock(), None

        with mock.patch.object(lastseen, "async_execute", new=mock.AsyncMock(side_effect=update_while_saving)):
            assert await cog.save()
        assert cog.dirty

    asyncio.run(run())


def test_lastseen_shutdown_keeps_dirty_when_revision_changes_during_final_save():
    async def run():
        cog = lastseen.LastSeenCog(mock.Mock())
        cog.cache_loaded = True
        cog.dirty = True

        async def concurrent_update():
            cog._revision += 1
            return True

        cog.save = mock.AsyncMock(side_effect=concurrent_update)
        await cog.cog_unload()
        assert cog.dirty

    asyncio.run(run())

def test_tts_discards_queued_message_from_previous_voice_channel():
    async def run():
        bot = mock.Mock()
        cog = alo_tts.AloTtsCog(bot)
        queue = asyncio.Queue()
        queue.put_nowait((101, "stale channel A"))
        cog.tts_queues[1] = queue
        cog.voice_sessions[1] = {"channel_id": 202, "intentional_leave": False}
        voice_client = mock.Mock()
        voice_client.is_connected.return_value = True
        voice_client.channel.id = 202
        bot.get_guild.return_value = mock.Mock(voice_client=voice_client)

        with mock.patch.object(alo_tts, "generate_tts_file") as generate:
            await cog._tts_worker(1)
        generate.assert_not_called()
        assert queue.empty()

    asyncio.run(run())


def test_tts_drops_message_if_voice_moves_while_audio_is_generated():
    async def run():
        bot = mock.Mock()
        cog = alo_tts.AloTtsCog(bot)
        queue = asyncio.Queue()
        queue.put_nowait((101, "message queued in channel A"))
        cog.tts_queues[1] = queue
        cog.voice_sessions[1] = {"channel_id": 101, "intentional_leave": False}
        voice_client = mock.Mock()
        voice_client.is_connected.return_value = True
        voice_client.is_playing.return_value = False
        voice_client.channel.id = 101
        bot.get_guild.return_value = mock.Mock(voice_client=voice_client)

        async def move_during_generation(*args):
            cog.voice_sessions[1]["channel_id"] = 202
            voice_client.channel.id = 202
            return "/missing/test-audio.mp3"

        bot.loop.run_in_executor = mock.AsyncMock(side_effect=move_during_generation)
        with mock.patch.object(alo_tts.os, "remove"):
            await cog._tts_worker(1)

        voice_client.play.assert_not_called()
        assert queue.empty()

    asyncio.run(run())

def test_tts_voice_move_updates_source_and_stops_current_audio():
    async def run():
        bot = mock.Mock()
        bot.user.id = 7
        cog = alo_tts.AloTtsCog(bot)
        voice_client = mock.Mock()
        voice_client.is_playing.return_value = True
        guild = mock.Mock(id=1, voice_client=voice_client)
        member = mock.Mock(id=7, guild=guild)
        before = mock.Mock(channel=mock.Mock(id=101))
        after = mock.Mock(channel=mock.Mock(id=202))
        cog.voice_sessions[1] = {"channel_id": 101, "intentional_leave": False}

        await cog.on_voice_state_update(member, before, after)

        assert cog.voice_sessions[1]["channel_id"] == 202
        voice_client.stop.assert_called_once()

    asyncio.run(run())

def test_alo_acknowledges_before_loading_tts_config():
    async def run():
        events = []
        bot = mock.Mock()
        cog = alo_tts.AloTtsCog(bot)
        bot.loop.create_task = mock.Mock()
        def discard_task(coroutine):
            coroutine.close()
            task = mock.Mock()
            task.done.return_value = False
            return task
        bot.loop.create_task.side_effect = discard_task
        voice = mock.Mock(id=202, name="Guild Voice")
        voice_client = mock.Mock(channel=voice)
        interaction = mock.Mock()
        interaction.guild = mock.Mock(id=1, voice_client=voice_client)
        interaction.user.display_name = "Member"
        interaction.response.defer = mock.AsyncMock(side_effect=lambda **kwargs: events.append("ack"))
        interaction.edit_original_response = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()

        async def load_config():
            events.append("load")
            return {"read_name": {}, "rejoin": {}}

        with mock.patch.object(alo_tts, "load_tts_config", new=mock.AsyncMock(side_effect=load_config)):
            await alo_tts.AloTtsCog.alo_cmd.callback(cog, interaction, voice, "hello")
        assert events[:2] == ["ack", "load"]
        interaction.edit_original_response.assert_awaited_once()

    asyncio.run(run())


def test_guildconfig_acknowledges_before_storage_read_and_write():
    async def run():
        events = []
        interaction = mock.Mock()
        interaction.response.defer = mock.AsyncMock(side_effect=lambda **kwargs: events.append("ack"))
        interaction.edit_original_response = mock.AsyncMock()
        cog = guildcheck.GuildCheckCog(mock.Mock())
        choice = mock.Mock(value="Asia")

        async def load_config():
            events.append("load")
            return {"guild_id": "", "region": "Asia"}

        async def save_config(config):
            events.append("save")

        with (
            mock.patch.object(guildcheck, "is_officer", return_value=True),
            mock.patch.object(guildcheck, "load_guildcheck_config", new=mock.AsyncMock(side_effect=load_config)),
            mock.patch.object(guildcheck, "save_guildcheck_config", new=mock.AsyncMock(side_effect=save_config)),
        ):
            await guildcheck.GuildCheckCog.guildconfig_cmd.callback(
                cog, interaction, guild_id="guild-1", region=choice
            )

        assert events == ["ack", "load", "save"]
        interaction.edit_original_response.assert_awaited_once()

    asyncio.run(run())


def test_utconfig_acknowledges_before_storage_read_and_write():
    async def run():
        events = []
        interaction = mock.Mock()
        interaction.guild = mock.Mock()
        interaction.user = mock.Mock()
        interaction.response.defer = mock.AsyncMock(side_effect=lambda **kwargs: events.append("ack"))
        interaction.edit_original_response = mock.AsyncMock()
        cog = update_translator.UpdateTranslatorCog(mock.Mock())
        choice = mock.Mock(value="off")

        async def load_config():
            events.append("load")
            return {"enabled": True, "channel_ids": []}

        async def save_config(config):
            events.append("save")

        with (
            mock.patch.object(update_translator, "is_officer", return_value=True),
            mock.patch.object(update_translator, "load_config", new=mock.AsyncMock(side_effect=load_config)),
            mock.patch.object(update_translator, "save_config", new=mock.AsyncMock(side_effect=save_config)),
        ):
            await update_translator.UpdateTranslatorCog.utconfig_cmd.callback(
                cog, interaction, enable=choice
            )

        assert events == ["ack", "load", "save"]
        interaction.edit_original_response.assert_awaited_once()

    asyncio.run(run())

def test_translator_reuses_and_unarchives_mapped_thread():
    class FakeThread:
        def __init__(self):
            self.id = 55
            self.archived = True
            self.edit = mock.AsyncMock()

    async def run():
        bot = mock.Mock()
        thread = FakeThread()
        bot.get_channel.return_value = None
        bot.fetch_channel = mock.AsyncMock(return_value=thread)
        cog = update_translator.UpdateTranslatorCog(bot)
        message = mock.Mock(id=10)
        message.create_thread = mock.AsyncMock()
        with (
            mock.patch.object(update_translator.discord, "Thread", FakeThread),
            mock.patch.object(update_translator, "load_config", new=mock.AsyncMock(return_value={"threads": {"10": "55"}})),
        ):
            result = await cog._get_or_create_thread(message, "update text")

        assert result is thread
        thread.edit.assert_awaited_once_with(archived=False)
        message.create_thread.assert_not_awaited()
        bot.fetch_channel.assert_awaited_once_with(55)

    asyncio.run(run())


def test_translator_serializes_concurrent_thread_creation_for_one_message():
    class FakeThread:
        def __init__(self):
            self.id = 55
            self.archived = False

    async def run():
        state = {"threads": {}}
        thread = FakeThread()
        bot = mock.Mock()
        bot.get_channel.side_effect = lambda channel_id: thread if int(channel_id) == thread.id else None
        cog = update_translator.UpdateTranslatorCog(bot)
        message = mock.Mock(id=10, thread=None)
        message.create_thread = mock.AsyncMock(return_value=thread)
        cog._make_title = mock.AsyncMock(return_value="Update")

        async def load_config():
            return deepcopy(state)

        async def save_config(config):
            state.clear()
            state.update(deepcopy(config))

        with (
            mock.patch.object(update_translator.discord, "Thread", FakeThread),
            mock.patch.object(update_translator, "load_config", new=mock.AsyncMock(side_effect=load_config)),
            mock.patch.object(update_translator, "save_config", new=mock.AsyncMock(side_effect=save_config)),
        ):
            first, second = await asyncio.gather(
                cog._get_or_create_thread(message, "update text"),
                cog._get_or_create_thread(message, "update text"),
            )

        assert first is thread and second is thread
        message.create_thread.assert_awaited_once()
        assert state["threads"]["10"] == 55

    asyncio.run(run())


def test_party_view_has_all_required_callbacks():
    party = _party()
    party["roles"] = ["Tank"]
    party["weapon_slots"] = {"Tank": [("Great Arcane", 1)]}
    party["slots"] = {"Tank": {"Great Arcane": []}}
    with mock.patch.dict(massing.active_parties, {party["id"]: party}, clear=True):
        view = massing.PartyView(party["id"])
        # Check all callback attributes exist
        assert hasattr(view, "save_template_callback")
        assert hasattr(view, "view_build_callback")
        assert hasattr(view, "fill_callback")
        assert hasattr(view, "leave_callback")
        assert hasattr(view, "add_callback")
        assert hasattr(view, "move_callback")
        assert hasattr(view, "kick_callback")
        assert hasattr(view, "note_callback")
        assert hasattr(view, "delete_callback")
        assert hasattr(view, "copy_callback")
        assert hasattr(view, "ping_callback")
        assert callable(view.make_join_callback("Tank", "Great Arcane"))


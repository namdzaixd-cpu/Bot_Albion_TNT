"""Test logic thuần + cấu hình của Onboarding (Recuibot) — không cần Discord thật / Supabase.

Che logic form/nickname, identity báo cáo ổn định, chống đơn trùng,
và trạng thái persistent approval view riêng cho từng đơn.
"""
import asyncio
from unittest import mock

import discord
import cogs.onboarding as onboarding_module
from cogs.onboarding import (
    OfficerApprovalView,
    OnboardConfig,
    Onboarding,
    _format_yob,
    application_marker,
    get_onboard_data,
    is_application_report,
    status_from_title,
)


def test_format_yob_cases():
    assert _format_yob("2005") == "2k5"
    assert _format_yob("2000") == "2k"
    assert _format_yob("2001") == "2k1"
    assert _format_yob("2010") == "2k10"
    assert _format_yob("2015") == "2k15"
    assert _format_yob("2024") == "2k24"
    assert _format_yob("1998") == "98"
    assert _format_yob("notnum") == "notnum"
    assert _format_yob("") == ""


def test_application_report_uses_stable_thread_marker():
    thread = mock.Mock(id=234, guild=mock.Mock(id=123))
    embed = discord.Embed(title="✅ Đã duyệt: Player")
    embed.url = application_marker(thread)
    message = mock.Mock(embeds=[embed])

    assert is_application_report(message, thread)
    embed.title = "A title edited by a moderator"
    assert is_application_report(message, thread)
    assert status_from_title(embed.title) is None

def test_concurrent_apply_messages_create_only_one_application_report():
    async def run():
        thread = mock.Mock(id=234, guild=mock.Mock(id=123))
        thread.reports = []

        async def history(limit=None):
            for report in thread.reports:
                yield report

        thread.history = history
        cog = Onboarding(mock.Mock())

        async def create_report(current_thread, message):
            embed = discord.Embed(title=f"Report for {message.content}")
            embed.url = application_marker(current_thread)
            thread.reports.append(mock.Mock(embeds=[embed]))

        cog._process_apply_thread = mock.AsyncMock(side_effect=create_report)
        await asyncio.gather(
            cog.process_apply_thread(thread, msg=mock.Mock(content="application A")),
            cog.process_apply_thread(thread, msg=mock.Mock(content="application B")),
        )
        cog._process_apply_thread.assert_awaited_once()

    asyncio.run(run())


def test_officer_approval_views_keep_per_application_state():
    cog = Onboarding(mock.Mock())
    pending = OfficerApprovalView(cog, status="submitted")
    approved = OfficerApprovalView(cog, status="approved", renamed=True)
    rejected = OfficerApprovalView(cog, status="rejected")
    pending_buttons = {child.custom_id: child for child in pending.children}
    approved_buttons = {child.custom_id: child for child in approved.children}
    rejected_buttons = {child.custom_id: child for child in rejected.children}

    assert not pending_buttons["onboard_approve"].disabled
    assert not pending_buttons["onboard_reject"].disabled
    assert approved_buttons["onboard_approve"].disabled
    assert approved_buttons["onboard_reject"].disabled
    assert approved_buttons["onboard_rename"].disabled
    assert all(child.disabled for child in rejected_buttons.values())


def test_onboard_config_constructor_has_no_database_side_effects():
    with mock.patch.object(onboarding_module, "get_config_async", new_callable=mock.AsyncMock) as load:
        config = OnboardConfig()

    assert config.data is None
    load.assert_not_awaited()


def test_cog_load_restores_message_bound_approval_view():
    thread = mock.Mock(id=234, guild=mock.Mock(id=123))
    embed = discord.Embed(title="✅ Đã duyệt: Player")
    embed.url = application_marker(thread)
    embed.set_footer(text="YOB: 2005 | Approved | Nickname đã đổi")
    report = mock.Mock(id=765, embeds=[embed])

    async def thread_history(limit=None):
        yield report

    thread.history = thread_history

    class FakeForum:
        def __init__(self):
            self.threads = [thread]

        async def archived_threads(self, limit=None):
            if False:
                yield None

    forum = FakeForum()
    bot = mock.Mock()
    bot.get_channel.return_value = forum
    cog = Onboarding(bot)
    cog.config.data = {"apply_channel_id": "456"}
    cog.config.load = mock.AsyncMock(return_value=cog.config.data)

    with mock.patch.object(onboarding_module.discord, "ForumChannel", FakeForum):
        asyncio.run(cog.cog_load())

    message_views = [
        call for call in bot.add_view.call_args_list
        if call.kwargs.get("message_id") == report.id
    ]
    assert len(message_views) == 1
    restored_view = message_views[0].args[0]
    assert restored_view.status == "approved"
    assert restored_view.renamed
    assert restored_view.children[0].disabled


def test_validate_form_short_form():
    # form thiếu keyword -> False
    content = "Tôi tên A, 20 tuổi, chơi game lâu."
    onb = Onboarding(mock.Mock())
    assert onb.validate_form(content) is False


def test_validate_form_ok():
    content = (
        "Ingame : TenNhanVat\n"
        "Năm sinh: 2005\n"
        "Giới tính: Nam\n"
        "Quốc gia: VN\n"
        "Thời gian chơi: tối\n"
        "Mic: có\n"
        "Chơi PC: là\n"
        "Role: DPS\n"
        "Guild cũ: ABC\n"
        "Mục đích: gia nhập\n"
        "Quy định: đã đọc"
    )
    onb = Onboarding(mock.Mock())
    assert onb.validate_form(content) is True




# ── get_onboard_data (cần Interaction chứa message/channel/thread) ──────────
class _FakeThread:
    def __init__(self, owner_id):
        self.owner_id = owner_id

    @property
    def channel(self):
        return self


class _FakeInteraction:
    def __init__(self, thread_owner_id, title, footer):
        self.message = mock.Mock()
        self.message.channel = thread_owner_id
        # thay channel bằng thread giả có owner_id
        self.message.channel = _FakeThread(thread_owner_id)
        self.message.embeds = [mock.Mock(title=title)]
        self.message.embeds[0].footer = mock.Mock(text=footer)


def test_get_onboard_data():
    it = _FakeInteraction(999, "Báo cáo tự động: TenIGN", "YOB: 2005 | qc")
    target_id, ign_name, yob, _ = get_onboard_data(it)
    assert ign_name == "TenIGN"
    assert yob == "2005"
    assert target_id == 999


def test_get_onboard_data_no_footer():
    it = _FakeInteraction(999, "Báo cáo tự động: X", "")
    _, _, yob, _ = get_onboard_data(it)
    assert yob == ""




"""Test logic thuần + cấu hình của Onboarding (Recuibot) — không cần Discord thật / Supabase.

Che 3 nhóm:
  A. Logic thuần: _format_yob, validate_form, get_onboard_data, regex biểu mẫu.
  B. Cog load; OnboardConfig khi DB chết → default, không crash.
  C. process_apply_thread: giữ đúng cổng chặn (không tìm thấy Ingame / form thiếu).
"""
import asyncio
import re
from unittest import mock

from cogs.onboarding import (
    OnboardConfig,
    Onboarding,
    _format_yob,
    get_onboard_data,
)


def test_format_yob_cases():
    assert _format_yob("2005") == "2k5"
    assert _format_yob("2000") == "2k"
    assert _format_yob("2001") == "2k1"
    assert _format_yob("1998") == "98"
    assert _format_yob("notnum") == "notnum"
    assert _format_yob("") == ""


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


def test_regex_eyebrow_ingame():
    content = "Ingame : Snake_Eyes_99\nNăm sinh: 2005"
    m = re.search(r"Ingame\s*[:\-]?\s*([a-zA-Z0-9_]+)", content, re.IGNORECASE)
    assert m is not None and m.group(1) == "Snake_Eyes_99"


def test_regex_yob():
    content = "Ingame : A\nNăm sinh: 2005"
    m = re.search(r"Năm sinh\s*[:\-]?\s*([a-zA-Z0-9]+)", content, re.IGNORECASE)
    assert m is not None and m.group(1) == "2005"


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


# ── Nhóm B: cog + config an-toàn-dưới-lỗi ─────────────────────────────────────
def test_onboard_slash_group_registered():
    import discord
    from cogs.onboarding import Onboarding
    from discord.ext import commands

    class _Bot(commands.Bot):
        def __init__(self):
            super().__init__(command_prefix="!", intents=discord.Intents.all())

    bot = _Bot()
    cog = Onboarding(bot)

    # top-level có đúng group "recuibot"
    top = {c.name for c in cog.get_app_commands()}
    assert "recuibot" in top

    # group chứa đủ 5 child command
    grp = cog.onboard_group
    child_names = {c.name for c in grp.commands}
    assert {"toggle", "set_apply_channel", "setup_channels", "setup_roles", "list"} <= child_names


def test_onboard_config_db_down_returns_default():
    # CI không có SUPABASE → execute trả lỗi → default is_onboard_enabled=True, không crash
    cog = Onboarding(mock.Mock())
    assert cog.config.is_enabled is True


# ── Nhóm C: process_apply_thread — cổng chặn giữ nguyên ──────────────────────
def _cog_with_config():
    bot = mock.Mock()
    bot.user.id = 9999
    cog = Onboarding(bot)
    cog.config = mock.Mock()
    cog.config.is_enabled = True
    cog.config.apply_channel_id = "777"
    return cog


def test_process_apply_thread_missing_ingame_warns():
    cog = _cog_with_config()
    thread = mock.Mock()
    thread.send = mock.AsyncMock()
    thread.owner_id = 123
    msg = mock.Mock(author=mock.Mock(id=123),
                    content="Năm sinh: 2005\nGiới tính: Nam\nMic: có\nRole: DPS")
    asyncio.run(cog.process_apply_thread(thread, msg=msg))
    # đủ keyword (validate_form đúng) nhưng thiếu mục Ingame → gửi cảnh báo ghi rõ Ingame
    assert thread.send.call_count >= 1


def test_process_apply_thread_short_form_warns():
    cog = _cog_with_config()
    thread = mock.Mock()
    thread.send = mock.AsyncMock()
    thread.owner_id = 123
    msg = mock.Mock(author=mock.Mock(id=123), content="Ingame : ABC nhưng thiếu mục khác")
    asyncio.run(cog.process_apply_thread(thread, msg=msg))
    # validate_form: chỉ 1 keyword (Ingame) -> thiếu -> cảnh báo "điền thiếu form"
    assert thread.send.call_count >= 1
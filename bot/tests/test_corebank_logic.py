"""Test logic thuần + luồng react của Core-Bank (không cần Discord thật / Supabase).

Che logic parse emoji và luồng on_message: thứ tự react, tách ảnh,
bỏ qua ngoài kênh Core hoặc khi tắt auto_react.

Không dùng thư viện external: mock nội bộ unittest để deterministic.
"""
import asyncio
from unittest import mock


class _Msg:
    def __init__(self, channel_id, attachments=None, author_bot=False, content=""):
        self.id = 111
        self.channel = mock.Mock(id=channel_id, parent_id=None)
        self.attachments = attachments or []
        self.author = mock.Mock()
        self.author.bot = author_bot
        self.content = content
        self.reply = mock.AsyncMock()
        self.delete = mock.AsyncMock()
        self.add_reaction = mock.AsyncMock()


def _msg_in(channel_id, atts=None):
    return _Msg(channel_id, atts)


async def _run_on_message(cog, message):
    # on_message là listener async — gọi trực tiếp trong event loop.
    # KHÔNG nuốt exception: test cần phát hiện bug thật, giống user dùng /coreadd.
    await cog.on_message(message)


def test_parse_emoji_input_custom():
    from cogs.corebank import parse_emoji_input
    key, display = parse_emoji_input("<:GreenCore:123456>")
    assert key == "123456"
    assert display == "<:GreenCore:123456>"


def test_parse_emoji_input_unicode():
    from cogs.corebank import parse_emoji_input
    assert parse_emoji_input("🟢") == ("🟢", "🟢")


def test_get_reaction_key():
    from cogs.corebank import get_reaction_key

    class _E:
        def __init__(self, id, name):
            self.id = id
            self.name = name

    assert get_reaction_key(_E(123, "x")) == "123"
    assert get_reaction_key(_E(None, "🟢")) == "🟢"


def test_sorted_emoji_keys_order():
    from cogs.corebank import _sorted_emoji_keys
    emoji_map = {
        "a": {"name": "A", "value": 100, "order": 2},
        "b": {"name": "B", "value": 50, "order": 0},
        "c": {"name": "C", "value": 300, "order": 0},
    }
    assert _sorted_emoji_keys(emoji_map) == ["b", "c", "a"]


def test_parse_emoji_input_non_custom_string():
    from cogs.corebank import parse_emoji_input
    # dạng có ":" nhưng không khớp <:name:id> → giữ nguyên raw
    assert parse_emoji_input(":smile:") == (":smile:", ":smile:")




def test_corebank_on_message_single_image_reacts_in_order():
    from cogs.corebank import CoreBankCog

    cog = CoreBankCog(mock.Mock())
    cog.config = {
        "core_channel_id": "100", "auto_react": True,
        "emoji_map": {"a": {"name": "A", "value": 100, "order": 2, "display": "<:a:100>"},
                      "b": {"name": "B", "value": 50, "order": 0, "display": "<:b:50>"}},
    }

    msg = _msg_in("100", [mock.Mock()])
    msg.channel.send = mock.AsyncMock()
    asyncio.run(_run_on_message(cog, msg))

    # 1 ảnh → react vào tin gốc. Code trả PartialEmoji.from_str → .name là chuỗi hiển thị.
    reacted = {c.args[0].name for c in msg.add_reaction.call_args_list}
    assert reacted == {"<:a:100>", "<:b:50>"}
    assert msg.delete.call_count == 0
    assert msg.channel.send.call_count == 0




def test_corebank_on_message_not_core_channel_no_react():
    from cogs.corebank import CoreBankCog

    cog = CoreBankCog(mock.Mock())
    cog.config = {
        "core_channel_id": "100", "auto_react": True,
        "emoji_map": {"a": {"name": "A", "value": 100, "order": 0, "display": "<:a:100>"}},
    }
    msg = _msg_in("999", [mock.Mock()])
    asyncio.run(_run_on_message(cog, msg))
    assert msg.add_reaction.call_count == 0
    assert msg.delete.call_count == 0


def test_corebank_on_message_auto_react_off_no_react():
    from cogs.corebank import CoreBankCog

    cog = CoreBankCog(mock.Mock())
    cog.config = {
        "core_channel_id": "100", "auto_react": False,
        "emoji_map": {"a": {"name": "A", "value": 100, "order": 0, "display": "<:a:100>"}},
    }
    msg = _msg_in("100", [mock.Mock()])
    asyncio.run(_run_on_message(cog, msg))
    assert msg.add_reaction.call_count == 0


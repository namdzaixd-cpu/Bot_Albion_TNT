import asyncio
from unittest import mock

import discord
import main as bot_main
from discord.ext import commands, tasks


def test_all_cogs_load_without_error():
    """Load toàn bộ extension khai báo trong bot/main.py (không dùng gateway thật)
    và kiểm tra các slash command chính đã đăng ký đúng — bắt lỗi import/setup
    của cog sớm, trước khi deploy.

    Chạy trong CI không có Discord token thật, nên cô lập khỏi event loop:
    - mock tree.sync (gọi API Discord)
    - mock SystemLogger.start (tạo background task cần loop)
    - patch discord.ext.tasks.Loop.start để task định kỳ không tự chạy
    """

    async def _run():
        bot = bot_main.TNCBot()
        # discord.py mới không cho truy cập bot.loop trước khi run().
        # Gán tạm loop cho test (CI chạy ngoài gateway thật).
        try:
            bot.loop = asyncio.get_event_loop()
        except RuntimeError:
            bot.loop = asyncio.new_event_loop()

        # Cô lập khỏi network / event loop
        async def _fake_sync(*a, **k):
            return []
        bot.tree.sync = _fake_sync

        with mock.patch.object(bot_main.SystemLogger, "start", lambda *a, **k: None), \
             mock.patch.object(tasks.Loop, "start", lambda self, *a, **k: None):
            # setup_hook() đã load toàn bộ EXTENSIONS + sync gateway (đã mock)
            await bot.setup_hook()

        slash_names = {c.name for c in bot.tree.walk_commands()}
        for expected in ("aboutme", "massing", "spcheck", "guildcheck", "alojoin", "corelist"):
            assert expected in slash_names, f"Thiếu slash command /{expected}"

        await bot.close()

    asyncio.run(_run())

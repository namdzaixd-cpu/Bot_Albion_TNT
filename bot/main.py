import os
import shutil
import signal
import asyncio

import discord
from discord.ext import commands

from core.config import BOT_SESSION_ID, GUILD_ID, TOKEN
from core.webserver import keep_alive
from core.system_logger import SystemLogger
from core.heartbeat import start as start_heartbeat

# ==============================================================================
# KHỞI TẠO BOT CORE
# ==============================================================================
EXTENSIONS = [
    "cogs.about",
    "cogs.siphoned",
    "cogs.massing",
    "cogs.lastseen",
    "cogs.guildcheck",
    "cogs.alo_tts",
    "cogs.corebank",
    "cogs.onboarding",
    "cogs.sync",
    "cogs.update_translator",
]


class TNCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=["!", "."], intents=intents, help_command=None)
        self._watchdog_task = None

    async def setup_hook(self):
        for extension in EXTENSIONS:
            await self.load_extension(extension)

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ Đã sync {len(synced)} slash commands vào guild!")

        # Bật ghi log hệ thống
        SystemLogger.start(self)
        # Bật heartbeat đập tim lên Supabase (dashboard đọc trạng thái online)
        start_heartbeat(self)

    async def close(self):
        task = self._watchdog_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await super().close()


bot = TNCBot()


# ==============================================================================
# WATCHDOG — TỰ ĐỘNG RESTART NẾU GATEWAY CHẾT QUÁ LÂU
# (Chống bệnh "bot câm, không phản hồi, phải restart thủ công")
# ==============================================================================
GATEWAY_DEAD_THRESHOLD = 180  # giây — nếu mất kết nối quá 3 phút thì tự restart


@bot.event
async def on_disconnect():
    print("⚠️ [Watchdog] Mất kết nối gateway Discord. Bắt đầu đếm ngược tự restart...")


@bot.event
async def on_resume():
    bot._dead_since = None
    print("✅ [Watchdog] Đã kết nối lại gateway. Hủy đếm ngược.")


async def _gateway_watchdog():
    await bot.wait_until_ready()
    loop = asyncio.get_running_loop()
    bot._dead_since = None
    while not bot.is_closed():
        await asyncio.sleep(15)
        if bot.is_closed():
            break
        if bot.latency == float("inf"):
            if bot._dead_since is None:
                bot._dead_since = loop.time()
            dead_for = loop.time() - bot._dead_since
            if dead_for >= GATEWAY_DEAD_THRESHOLD:
                print(f"🔥 [Watchdog] Gateway chết {dead_for:.0f}s — TỰ ĐỘNG RESTART!")
                os.kill(os.getpid(), signal.SIGTERM)
        else:
            bot._dead_since = None


@bot.event
async def on_ready():
    print(f"✅ Bot đã hoạt động: {bot.user} | ID: {bot.user.id}")
    print(f"🔍 [Check] ffmpeg path: {shutil.which('ffmpeg')}")
    bot_name = os.getenv("BOT_NAME", "TNT")
    print(f"✅ {bot_name} v40 [Siphoned + Massing + GuildCheck + ALO-TTS + CoreBank] Online! Session: {BOT_SESSION_ID}")
    task = bot._watchdog_task
    if task is None or task.done():
        bot._watchdog_task = asyncio.create_task(_gateway_watchdog())


if __name__ == "__main__":
    keep_alive(bot)
    bot.run(TOKEN)

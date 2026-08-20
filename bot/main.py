import os
import shutil
import signal
import asyncio

import discord
from discord.ext import commands

from core.config import BOT_SESSION_ID, GUILD_ID, TOKEN
from core.storage import restore_from_github
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
]


class TNCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=["!", "."], intents=intents, help_command=None)

    async def setup_hook(self):
        restore_from_github()  # Kéo data JSON từ GitHub về trước khi load cog
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
    print("✅ [Watchdog] Đã kết nối lại gateway. Hủy đếm ngược.")


async def _gateway_watchdog():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(15)
        if bot.is_closed():
            break
        # Nếu đang mất kết nối (latency = infinity) quá ngưỡng -> restart
        if bot.latency == float("inf"):
            # cần đếm ngược liên tục -> dùng biến riêng
            if not hasattr(bot, "_dead_since"):
                bot._dead_since = asyncio.get_event_loop().time()
            dead_for = asyncio.get_event_loop().time() - bot._dead_since
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
    # Khởi chạy watchdog sau khi bot sẵn sàng
    bot.loop.create_task(_gateway_watchdog())


if __name__ == "__main__":
    keep_alive(bot)
    bot.run(TOKEN)

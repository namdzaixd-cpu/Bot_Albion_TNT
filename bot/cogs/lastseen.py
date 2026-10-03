import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands

from core.db import async_execute

# ==============================================================================
# HỆ THỐNG FILTER THÀNH VIÊN (LastSeen)
# ==============================================================================

class LastSeenCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache = {}
        self.dirty = False
        self._revision = 0
        self._flush_task = None
        self.cache_loaded = False

    async def _load_cache(self):
        try:
            response, error = await async_execute(
                lambda client: client.table("user_activity").select("user_id, last_seen")
            )
            if error:
                raise RuntimeError(error)
            for row in response.data or []:
                self.cache.setdefault(str(row["user_id"]), row["last_seen"])
            self.cache_loaded = True
            return True
        except Exception as error:
            print(f"Error loading user_activity from Supabase: {error}")
            return False

    async def cog_load(self):
        await self._load_cache()

    async def cog_unload(self):
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        if self.dirty:
            if not self.cache_loaded or not await self.save() or self.dirty:
                print("❌ [LastSeen] Lưu cuối kỳ thất bại; dữ liệu vẫn dirty.")

    @commands.Cog.listener()
    async def on_ready(self):
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def save(self):
        if not self.cache_loaded:
            return False
        if not self.cache:
            return True
        revision = self._revision
        records = [
            {"user_id": str(user_id), "last_seen": timestamp}
            for user_id, timestamp in self.cache.items()
        ]
        try:
            for start in range(0, len(records), 1000):
                chunk = records[start:start + 1000]
                _, error = await async_execute(
                    lambda client, chunk=chunk: client.table("user_activity").upsert(chunk)
                )
                if error:
                    print(f"Error saving user_activity chunk: {error}")
                    return False
        except Exception as error:
            print(f"Error saving user_activity to Supabase: {error}")
            return False
        if self._revision == revision:
            self.dirty = False
        return True

    async def _flush_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(300)
            if self.dirty:
                if not self.cache_loaded and not await self._load_cache():
                    continue
                if await self.save() and not self.dirty:
                    print("💾 [LastSeen] Đã lưu xuống Supabase (định kỳ 5 phút).")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        self.cache[str(message.author.id)] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self._revision += 1
        self.dirty = True


async def setup(bot: commands.Bot):
    await bot.add_cog(LastSeenCog(bot))

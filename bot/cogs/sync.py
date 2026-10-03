import discord
from discord.ext import commands
from core.config import GUILD_ID
from core.db import async_execute
class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _upsert_channel(self, channel: discord.abc.GuildChannel):
        try:
            data = {
                "id": str(channel.id),
                "name": channel.name,
                "type": str(channel.type),
                "guild_id": str(channel.guild.id)
            }
            # Supabase upsert uses the primary key 'id' to resolve conflicts
            _, err = await async_execute(lambda c: c.table("discord_channels").upsert(data))
            if err:
                print(f"Error upserting channel {channel.name}: {err}")
        except Exception as e:
            print(f"Error upserting channel {channel.name}: {e}")

    async def _delete_channel(self, channel_id: int):
        try:
            _, err = await async_execute(lambda c: c.table("discord_channels").delete().eq("id", str(channel_id)))
            if err:
                print(f"Error deleting channel {channel_id}: {err}")
        except Exception as e:
            print(f"Error deleting channel {channel_id}: {e}")

    async def _upsert_role(self, role: discord.Role):
        try:
            data = {
                "id": str(role.id),
                "name": role.name,
                "color": str(role.color),
                "guild_id": str(role.guild.id)
            }
            _, err = await async_execute(lambda c: c.table("discord_roles").upsert(data))
            if err:
                print(f"Error upserting role {role.name}: {err}")
        except Exception as e:
            print(f"Error upserting role {role.name}: {e}")

    async def _delete_role(self, role_id: int):
        try:
            _, err = await async_execute(lambda c: c.table("discord_roles").delete().eq("id", str(role_id)))
            if err:
                print(f"Error deleting role {role_id}: {err}")
        except Exception as e:
            print(f"Error deleting role {role_id}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        print("🔄 Đang đồng bộ Channels và Roles lên Supabase...")
        guild = self.bot.get_guild(int(GUILD_ID))
        if guild:
            # Upsert Guild Config trước để tránh lỗi Foreign Key
            try:
                _, err = await async_execute(lambda c: c.table("guild_config").upsert(
                    {"guild_id": str(guild.id)}, on_conflict="guild_id"))
                if err:
                    print(f"Lỗi khi tạo guild_config trong sync: {err}")
            except Exception as e:
                print(f"Lỗi khi tạo guild_config trong sync: {e}")

            # Sync channels
            for channel in guild.channels:
                await self._upsert_channel(channel)
            # Sync roles
            for role in guild.roles:
                await self._upsert_role(role)
        print("✅ Hoàn tất đồng bộ Channels và Roles!")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if str(channel.guild.id) == str(GUILD_ID):
            await self._upsert_channel(channel)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if str(after.guild.id) == str(GUILD_ID):
            await self._upsert_channel(after)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if str(channel.guild.id) == str(GUILD_ID):
            await self._delete_channel(channel.id)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if str(role.guild.id) == str(GUILD_ID):
            await self._upsert_role(role)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if str(after.guild.id) == str(GUILD_ID):
            await self._upsert_role(after)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if str(role.guild.id) == str(GUILD_ID):
            await self._delete_role(role.id)

async def setup(bot):
    await bot.add_cog(Sync(bot))

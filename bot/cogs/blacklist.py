import discord
from discord import app_commands
from discord.ext import commands
import datetime
import aiohttp
from typing import Optional

from core.permissions import is_officer
from core.db import async_execute

class GlobalBlacklist:
    async def check_blacklist(self, discord_id: str, ingame_id: str) -> Optional[dict]:
        try:
            res, err = await async_execute(lambda c: c.table("blacklist").select("*")
                               .or_(f"discord_id.eq.{discord_id},ingame_id.eq.{ingame_id}"))
            if err:
                print(f"[Error] Lỗi khi check_blacklist Supabase: {err}")
                return None
            if res and res.data:
                return res.data[0]
        except Exception as e:
            print(f"[Error] Lỗi khi check_blacklist Supabase: {e}")
        return None

    async def add_entry(self, discord_id: str, ingame_name: str, ingame_id: str, reason: str, officer_id: str, guild_id: str) -> bool:
        try:
            new_entry = {
                "discord_id": str(discord_id),
                "ingame_name": ingame_name,
                "ingame_id": str(ingame_id),
                "reason": reason,
                "added_by_discord_id": str(officer_id),
                "source_guild_id": str(guild_id),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            }
            _, err = await async_execute(lambda c: c.table("blacklist").upsert(new_entry))
            if err:
                print(f"[Error] Lỗi khi add_entry Supabase: {err}")
                return False
            return True
        except Exception as e:
            print(f"[Error] Lỗi khi add_entry Supabase: {e}")
            return False

    async def remove_entry(self, identifier: str) -> bool:
        try:
            res, err = await async_execute(lambda c: c.table("blacklist").select("*")
                               .or_(f"discord_id.eq.{identifier},ingame_name.ilike.{identifier}"))
            if err:
                print(f"[Error] Lỗi khi remove_entry query: {err}")
                return False
            if res and res.data:
                for entry in res.data:
                    _, e2 = await async_execute(lambda c: c.table("blacklist").delete().eq("discord_id", entry["discord_id"]))
                    if e2:
                        print(f"[Error] Lỗi khi delete entry: {e2}")
                        return False
                return True
        except Exception as e:
            print(f"[Error] Lỗi khi remove_entry Supabase: {e}")
        return False

    async def get_all(self):
        try:
            res, err = await async_execute(lambda c: c.table("blacklist").select("*"))
            if err:
                print(f"[Error] Lỗi khi get_all Supabase: {err}")
                return []
            return res.data or []
        except Exception as e:
            print(f"[Error] Lỗi khi get_all Supabase: {e}")
            return []


class BlacklistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.blacklist_db = GlobalBlacklist()
        
    async def fetch_albion_player(self, ign: str):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://gameinfo-sgp.albiononline.com/api/gameinfo/search?q={ign}") as resp:
                    if resp.status != 200: return None
                    data = await resp.json()
                    players = data.get("players", [])
                    if not players: return None
                    
                    player = next((p for p in players if p["Name"].lower() == ign.lower()), None)
                    if not player: return None
                    return player
        except Exception as e:
            print(f"[Error] {e}")
            return None

    blacklist_group = app_commands.Group(name="blacklist", description="Hệ thống Global Blacklist liên minh")

    @blacklist_group.command(name="add", description="Thêm một người chơi vào danh sách đen")
    async def blacklist_add(self, interaction: discord.Interaction, user: discord.Member, ingame_name: str, reason: str):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được quyền dùng lệnh này!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        player_data = await self.fetch_albion_player(ingame_name)
        if not player_data:
            await interaction.followup.send(f"❌ Không tìm thấy nhân vật `{ingame_name}` trên hệ thống Albion SGP. Vui lòng kiểm tra lại tên.")
            return
            
        ingame_id = player_data["Id"]
        
        success = await self.blacklist_db.add_entry(
            discord_id=user.id,
            ingame_name=player_data["Name"],
            ingame_id=ingame_id,
            reason=reason,
            officer_id=interaction.user.id,
            guild_id=interaction.guild.id
        )
        if not success:
            await interaction.followup.send("❌ Không lưu được blacklist; vui lòng thử lại khi DB hoạt động.")
            return
        
        embed = discord.Embed(title="🚨 Đã thêm vào Blacklist", color=discord.Color.red())
        embed.add_field(name="Discord", value=f"<@{user.id}> ({user.id})", inline=False)
        embed.add_field(name="Ingame", value=f"{player_data['Name']}", inline=True)
        embed.add_field(name="Lý do", value=reason, inline=False)
        embed.set_footer(text=f"Thêm bởi {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed)


    @blacklist_group.command(name="remove", description="Xóa một người chơi khỏi danh sách đen (bằng Discord ID hoặc Ingame Name)")
    async def blacklist_remove(self, interaction: discord.Interaction, identifier: str):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được quyền dùng lệnh này!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        success = await self.blacklist_db.remove_entry(identifier)
        if success:
            await interaction.followup.send(f"✅ Đã gỡ bỏ `{identifier}` khỏi Blacklist.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Không xóa được hoặc không tìm thấy `{identifier}` trong Blacklist.", ephemeral=True)


    @blacklist_group.command(name="view", description="Xem danh sách đen hiện tại")
    async def blacklist_view(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được quyền xem Blacklist!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        entries = await self.blacklist_db.get_all()
        if not entries:
            await interaction.followup.send("✅ Danh sách đen hiện đang trống.", ephemeral=True)
            return
            
        embed = discord.Embed(title="📜 Global Blacklist", color=discord.Color.dark_red())
        
        for entry in entries:
            discord_mention = f"<@{entry['discord_id']}>"
            ingame = entry['ingame_name']
            reason = entry['reason']
            embed.add_field(name=f"Ingame: {ingame}", value=f"Discord: {discord_mention}\nLý do: {reason}", inline=False)
            
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistCog(bot))

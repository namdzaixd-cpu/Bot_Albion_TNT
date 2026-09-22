import io
import os
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from core.config import STORAGE_DIR
from core.permissions import is_officer
from core.storage import load_json, save_json

# ==============================================================================
# HỆ THỐNG GUILDCHECK & QUẢN LÝ THÀNH VIÊN IN-GAME
# ==============================================================================
GUILDCHECK_CONFIG_FILE = os.path.join(STORAGE_DIR, "tnc_guildcheck_v1.json")
REGION_API_BASE = {
    "Americas": "https://gameinfo.albiononline.com/api/gameinfo",
    "Asia": "https://gameinfo-sgp.albiononline.com/api/gameinfo",
    "Europe": "https://gameinfo-ams.albiononline.com/api/gameinfo",
}

GUILDCHECK_CONFIG_DEFAULT = lambda: {"guild_id": "", "region": "Asia"}

def load_guildcheck_config():
    return load_json(GUILDCHECK_CONFIG_FILE, GUILDCHECK_CONFIG_DEFAULT)

def save_guildcheck_config(data):
    save_json(data, GUILDCHECK_CONFIG_FILE)

def format_fame(val):
    """Định dạng Fame số lớn (K, M, B) cho dễ đọc."""
    try:
        val = float(val or 0)
        if abs(val) >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f}B"
        if abs(val) >= 1_000_000:
            return f"{val / 1_000_000:.2f}M"
        if abs(val) >= 1_000:
            return f"{val / 1_000:.1f}K"
        return f"{int(val)}"
    except Exception:
        return "0"

async def albion_search_player(region, name):
    """Tìm player khớp TÊN TUYỆT ĐỐI trên đúng region. Trả None nếu không thấy."""
    base = REGION_API_BASE.get(region)
    if not base or not name:
        return None
    url = f"{base}/search?q={name}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
    except Exception as e:
        print(f"[albion_search_player] Lỗi: {e}")
        return None
    name_lower = name.strip().lower()
    for p in data.get("players", []):
        if (p.get("Name") or "").strip().lower() == name_lower:
            return p
    return None

async def albion_get_guild_members(region, guild_id):
    """Lấy danh sách toàn bộ thành viên trong Guild từ API SBI."""
    base = REGION_API_BASE.get(region)
    if not base or not guild_id:
        return None
    url = f"{base}/guilds/{guild_id}/members"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                if isinstance(data, list):
                    return data
                return None
    except Exception as e:
        print(f"[albion_get_guild_members] Lỗi: {e}")
        return None

async def albion_get_guild_info(region, guild_id):
    """Lấy thông tin tổng quan của Guild từ API SBI."""
    base = REGION_API_BASE.get(region)
    if not base or not guild_id:
        return None
    url = f"{base}/guilds/{guild_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[albion_get_guild_info] Lỗi: {e}")
        return None


# ==============================================================================
# VIEW PHÂN TRANG DANH SÁCH THÀNH VIÊN
# ==============================================================================
class GuildMembersPaginationView(discord.ui.View):
    def __init__(self, author: discord.User, members: list, guild_name: str, region: str, sort_label: str):
        super().__init__(timeout=180)
        self.author = author
        self.members = members
        self.guild_name = guild_name
        self.region = region
        self.sort_label = sort_label
        self.per_page = 12
        self.current_page = 0
        self.total_pages = max(1, (len(members) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.first_btn.disabled = (self.current_page == 0)
        self.prev_btn.disabled = (self.current_page == 0)
        self.page_indicator.label = f"Trang {self.current_page + 1}/{self.total_pages} ({len(self.members)} TV)"
        self.next_btn.disabled = (self.current_page >= self.total_pages - 1)
        self.last_btn.disabled = (self.current_page >= self.total_pages - 1)

    def get_embed(self) -> discord.Embed:
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_items = self.members[start_idx:end_idx]

        embed = discord.Embed(
            title=f"🛡️ Danh Sách Thành Viên Guild: {self.guild_name}",
            description=(
                f"🌍 **Khu vực:** `{self.region}` | 📊 **Sắp xếp theo:** `{self.sort_label}`\n"
                f"👥 **Tổng số thành viên:** **{len(self.members)}**\n"
                "───────────────────────────"
            ),
            color=0x3498db
        )

        lines = []
        for i, m in enumerate(page_items, start=start_idx + 1):
            name = m.get("Name", "Unknown")
            kf = format_fame(m.get("KillFame", 0))
            df = format_fame(m.get("DeathFame", 0))
            lines.append(f"`#{i:03d}` **{name}** — ⚔️ `{kf}` | 💀 `{df}`")

        embed.add_field(
            name="📋 Danh sách thành viên (IGN — Kill Fame | Death Fame)",
            value="\n".join(lines) if lines else "📭 Không có dữ liệu.",
            inline=False
        )
        embed.set_footer(text=f"Trang {self.current_page + 1}/{self.total_pages} • Dữ liệu từ Albion Online Official API")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Bạn không phải người dùng lệnh này!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def first_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Trang 1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


# ==============================================================================
# COG CHÍNH
# ==============================================================================
class GuildCheckCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="guildconfig", description="Cấu hình Guild ID và Khu vực cho máy chủ (Officer only)")
    @app_commands.describe(
        guild_id="Guild ID Albion (lấy từ URL killboard guild)",
        region="Khu vực máy chủ (Asia, Americas, Europe)"
    )
    @app_commands.choices(region=[
        app_commands.Choice(name="Châu Á (East)", value="Asia"),
        app_commands.Choice(name="Châu Mỹ (West)", value="Americas"),
        app_commands.Choice(name="Châu Âu (EU)", value="Europe")
    ])
    async def guildconfig_cmd(
        self,
        interaction: discord.Interaction,
        guild_id: str = None,
        region: app_commands.Choice[str] = None
    ):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        config = load_guildcheck_config()
        if guild_id:
            config["guild_id"] = guild_id.strip()
        if region:
            config["region"] = region.value
        save_guildcheck_config(config)

        lines = [f"🆔 Guild ID: `{config.get('guild_id') or 'chưa cấu hình'}`"]
        lines.append(f"🌍 Region: `{config.get('region') or 'Asia'}`")
        await interaction.response.send_message("✅ Đã lưu cấu hình GuildCheck:\n" + "\n".join(lines), ephemeral=True)

    @app_commands.command(name="guildcheck", description="Tra cứu xem một thành viên có ở trong Guild hay không")
    @app_commands.describe(ign="Tên nhân vật trong game (chính xác)")
    async def guildcheck_cmd(self, interaction: discord.Interaction, ign: str):
        config = load_guildcheck_config()
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")
        
        if not guild_id:
            return await interaction.response.send_message("❌ Chưa cấu hình Guild ID! Vui lòng nhờ Officer dùng `/guildconfig`.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=False)
        
        player = await albion_search_player(region, ign)
        
        if player is None:
            embed = discord.Embed(
                title="🔍 Kết Quả Tra Cứu", 
                description=f"❌ **Không tìm thấy người chơi `{ign}`** trên khu vực `{region}`.\nVui lòng kiểm tra lại chính tả.", 
                color=0xe74c3c
            )
            return await interaction.followup.send(embed=embed)
            
        player_guild_id = player.get("GuildId", "")
        player_guild_name = player.get("GuildName", "Không có guild")
        
        if player_guild_id == guild_id:
            embed = discord.Embed(
                title="✅ Thành Viên Hợp Lệ", 
                description=f"Người chơi **{player.get('Name')}** hiện **ĐANG** ở trong guild của chúng ta.", 
                color=0x2ecc71
            )
        else:
            embed = discord.Embed(
                title="🚨 Phát Hiện Ngoại Lai", 
                description=f"Người chơi **{player.get('Name')}** hiện **KHÔNG** ở trong guild.\nĐang ở guild: `{player_guild_name}`", 
                color=0xe67e22
            )
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="guildmembers", description="Lấy danh sách thành viên Guild in-game từ Albion Online API")
    @app_commands.describe(
        sort_by="Tiêu chí sắp xếp danh sách",
        export_file="Xuất file danh sách đầy đủ (.txt) đính kèm"
    )
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="⚔️ Kill Fame (Cao -> Thấp)", value="kill_fame"),
        app_commands.Choice(name="💀 Death Fame (Cao -> Thấp)", value="death_fame"),
        app_commands.Choice(name="🔤 Tên IGN (A -> Z)", value="name"),
    ])
    async def guildmembers_cmd(
        self,
        interaction: discord.Interaction,
        sort_by: app_commands.Choice[str] = None,
        export_file: bool = False
    ):
        config = load_guildcheck_config()
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")

        if not guild_id:
            return await interaction.response.send_message(
                "❌ Chưa cấu hình Guild ID! Vui lòng nhờ Officer dùng `/guildconfig` để cài đặt.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)

        members = await albion_get_guild_members(region, guild_id)
        if members is None:
            return await interaction.followup.send(
                "❌ Không thể lấy dữ liệu thành viên từ Albion API. Vui lòng kiểm tra lại Guild ID hoặc thử lại sau.",
                ephemeral=True
            )

        if not members:
            return await interaction.followup.send("📭 Guild hiện tại chưa có thành viên nào trên hệ thống API.")

        # Lấy tên guild từ member đầu tiên hoặc info
        guild_name = members[0].get("GuildName") or "TNC Guild"

        # Sắp xếp
        sort_key = sort_by.value if sort_by else "kill_fame"
        if sort_key == "kill_fame":
            members.sort(key=lambda x: x.get("KillFame") or 0, reverse=True)
            sort_label = "⚔️ Kill Fame (Cao -> Thấp)"
        elif sort_key == "death_fame":
            members.sort(key=lambda x: x.get("DeathFame") or 0, reverse=True)
            sort_label = "💀 Death Fame (Cao -> Thấp)"
        elif sort_key == "name":
            members.sort(key=lambda x: (x.get("Name") or "").strip().lower())
            sort_label = "🔤 Tên IGN (A -> Z)"
        else:
            sort_label = "Mặc định"

        view = GuildMembersPaginationView(
            author=interaction.user,
            members=members,
            guild_name=guild_name,
            region=region,
            sort_label=sort_label
        )
        embed = view.get_embed()

        file_attachment = None
        if export_file:
            txt_lines = [
                f"DANH SÁCH THÀNH VIÊN GUILD: {guild_name}",
                f"Khu vực: {region} | Guild ID: {guild_id}",
                f"Thời gian xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                f"Tổng số thành viên: {len(members)}",
                "=" * 60,
                f"{'STT':<5} {'Tên Nhân Vật (IGN)':<25} {'Kill Fame':<15} {'Death Fame':<15}",
                "-" * 60
            ]
            for idx, m in enumerate(members, 1):
                name = m.get("Name", "Unknown")
                kf = format_fame(m.get("KillFame", 0))
                df = format_fame(m.get("DeathFame", 0))
                txt_lines.append(f"{idx:<5} {name:<25} {kf:<15} {df:<15}")
            
            content_bytes = "\n".join(txt_lines).encode("utf-8")
            file_attachment = discord.File(
                fp=io.BytesIO(content_bytes),
                filename=f"guild_members_{guild_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

        if file_attachment:
            await interaction.followup.send(embed=embed, view=view, file=file_attachment)
        else:
            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="guildaudit", description="Đối soát chéo thành viên In-game vs Thành viên Discord (Officer only)")
    async def guildaudit_cmd(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền Officer để dùng lệnh này!", ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong server Discord.", ephemeral=True)

        config = load_guildcheck_config()
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")

        if not guild_id:
            return await interaction.response.send_message(
                "❌ Chưa cấu hình Guild ID! Vui lòng dùng `/guildconfig` trước.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=False)

        members = await albion_get_guild_members(region, guild_id)
        if members is None:
            return await interaction.followup.send("❌ Không thể lấy dữ liệu thành viên từ Albion API. Vui lòng thử lại sau.")

        guild_name = members[0].get("GuildName") if members else "TNC Guild"

        # Lập map in-game IGN -> member data
        ingame_map = {}
        for m in members:
            ign = (m.get("Name") or "").strip()
            if ign:
                ingame_map[ign.lower()] = ign

        # Lập map discord name / display_name
        discord_users = {}
        for dm in guild.members:
            if dm.bot:
                continue
            disp = dm.display_name.strip()
            name_only = disp
            # Tách các định dạng phổ biến: [TAG] Name, TNC | Name, Name (IGN)
            for sep in ["[", "]", "|", "(", ")"]:
                name_only = name_only.replace(sep, " ")
            tokens = [t.strip().lower() for t in name_only.split() if t.strip()]
            discord_users[dm.id] = {
                "member": dm,
                "display_name": disp,
                "tokens": tokens,
                "raw_lower": disp.lower()
            }

        # Đối soát
        matched_ingame = set()
        matched_discord = set()

        for lower_ign, orig_ign in ingame_map.items():
            for d_id, d_info in discord_users.items():
                if lower_ign == d_info["raw_lower"] or lower_ign in d_info["tokens"]:
                    matched_ingame.add(orig_ign)
                    matched_discord.add(d_id)
                    break

        unmatched_ingame = [orig for lower, orig in ingame_map.items() if orig not in matched_ingame]
        unmatched_ingame.sort()

        # Tạo file báo cáo chi tiết
        report_lines = [
            f"BÁO CÁO ĐỐI SOÁT THÀNH VIÊN GUILD: {guild_name}",
            f"Khu vực: {region} | Guild ID: {guild_id}",
            f"Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"Tổng thành viên In-game: {len(ingame_map)}",
            f"Tổng thành viên Discord (không tính bot): {len(discord_users)}",
            f"Khớp thành công: {len(matched_ingame)}",
            f"In-game nhưng chưa tìm thấy trên Discord: {len(unmatched_ingame)}",
            "=" * 60,
            "",
            f"--- 🚩 DANH SÁCH IN-GAME CHƯA KHỚP TRÊN DISCORD ({len(unmatched_ingame)} người) ---",
            "Ghi chú: Thành viên có thể chưa vào server hoặc đặt Nickname Discord khác IGN."
        ]
        for idx, ign in enumerate(unmatched_ingame, 1):
            report_lines.append(f"{idx:<4}. {ign}")

        report_lines.append("")
        report_lines.append(f"--- 🟢 DANH SÁCH ĐÃ KHỚP ({len(matched_ingame)} người) ---")
        for idx, ign in enumerate(sorted(matched_ingame), 1):
            report_lines.append(f"{idx:<4}. {ign}")

        content_bytes = "\n".join(report_lines).encode("utf-8")
        report_file = discord.File(
            fp=io.BytesIO(content_bytes),
            filename=f"guild_audit_{guild_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        embed = discord.Embed(
            title="📊 Báo Cáo Đối Soát Nhân Sự Guild (In-Game vs Discord)",
            description=(
                f"🛡️ **Guild:** `{guild_name}` | 🌍 **Region:** `{region}`\n"
                f"⏰ **Thời gian:** `{datetime.now().strftime('%d/%m/%Y %H:%M')}`\n"
                "───────────────────────────"
            ),
            color=0x2ecc71 if len(unmatched_ingame) == 0 else 0xe67e22
        )
        embed.add_field(name="👥 Tổng In-Game", value=f"**{len(ingame_map)}** TV", inline=True)
        embed.add_field(name="💬 Tổng Discord", value=f"**{len(discord_users)}** TV", inline=True)
        embed.add_field(name="🟢 Đã Khớp", value=f"**{len(matched_ingame)}** TV", inline=True)
        embed.add_field(
            name="🚩 In-Game Chưa Khớp Discord",
            value=f"**{len(unmatched_ingame)}** TV (Xem chi tiết trong file đính kèm)",
            inline=False
        )

        sample_unmatched = unmatched_ingame[:15]
        if sample_unmatched:
            more = f"\n*...và {len(unmatched_ingame) - 15} người khác*" if len(unmatched_ingame) > 15 else ""
            embed.add_field(
                name="⚠️ Ví dụ thành viên in-game chưa khớp Nickname:",
                value=", ".join(f"`{x}`" for x in sample_unmatched) + more,
                inline=False
            )

        embed.set_footer(text="Officer tải file đính kèm để xem danh sách chi tiết từng nhóm.")
        await interaction.followup.send(embed=embed, file=report_file)

    @app_commands.command(name="newmembers", description="Liệt kê thành viên mới gia nhập guild trong N ngày gần nhất (mặc định 7)")
    @app_commands.describe(days="Số ngày gần nhất cần lọc (mặc định 7, tối đa 90)")
    async def newmembers(self, interaction: discord.Interaction, days: int = 7):
        await interaction.response.defer(ephemeral=False)
        try:
            guild = interaction.guild
            if guild is None:
                return await interaction.followup.send("❌ Lệnh này chỉ dùng được trong server.")
            days = max(1, min(days, 90))
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            members = []
            for m in guild.members:
                j = m.joined_at
                if j and j >= cutoff:
                    members.append((m.display_name, j))
            members.sort(key=lambda x: x[1], reverse=True)
            if not members:
                return await interaction.followup.send(
                    f"📭 Trong {days} ngày qua **không có** thành viên mới nào gia nhập guild."
                )
            lines = []
            for name, j in members[:30]:
                jd = j.strftime("%d/%m/%Y")
                lines.append(f"• **{name}** — vào ngày {jd}")
            more = "" if len(members) <= 30 else f"\n...và {len(members)-30} người khác"
            await interaction.followup.send(
                f"🆕 **Thành viên mới trong {days} ngày qua ({len(members)} người):**\n"
                + "\n".join(lines) + more
            )
        except Exception as e:
            print(f"[newmembers] Lỗi: {e}")
            await interaction.followup.send(f"❌ Lỗi khi lấy danh sách thành viên mới: `{e}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(GuildCheckCog(bot))

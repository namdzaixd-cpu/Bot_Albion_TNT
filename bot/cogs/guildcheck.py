import asyncio
import io
import os
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp

from core.config import GUILD_ID, STORAGE_DIR
from core.db import async_execute
from core.permissions import is_officer
from core.storage import load_json_async, save_json_async

# ==============================================================================
# HỆ THỐNG GUILDCHECK & QUẢN LÝ THÀNH VIÊN IN-GAME
# ==============================================================================
GUILDCHECK_CONFIG_FILE = os.path.join(STORAGE_DIR, "tnc_guildcheck_v1.json")
GUILDCHECK_SNAPSHOT_FILE = os.path.join(STORAGE_DIR, "tnc_guildcheck_snapshot_v1.json")
REGION_API_BASE = {
    "Americas": "https://gameinfo.albiononline.com/api/gameinfo",
    "Asia": "https://gameinfo-sgp.albiononline.com/api/gameinfo",
    "Europe": "https://gameinfo-ams.albiononline.com/api/gameinfo",
}

GUILDCHECK_CONFIG_DEFAULT = lambda: {
    "guild_id": "",
    "region": "Asia",
    "auto_strip_enabled": False,
    "log_channel_id": "",
    "guest_role_id": "",
}
GUILDCHECK_SNAPSHOT_DEFAULT = lambda: {
    "guild_id": "",
    "region": "Asia",
    "updated_at": "",
    "members": {},
}


async def load_guildcheck_config():
    return await load_json_async(GUILDCHECK_CONFIG_FILE, GUILDCHECK_CONFIG_DEFAULT)


async def save_guildcheck_config(data):
    return await save_json_async(data, GUILDCHECK_CONFIG_FILE)


async def load_guildcheck_snapshot():
    return await load_json_async(GUILDCHECK_SNAPSHOT_FILE, GUILDCHECK_SNAPSHOT_DEFAULT)


async def save_guildcheck_snapshot(data):
    return await save_json_async(data, GUILDCHECK_SNAPSHOT_FILE)


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


async def albion_get_player_by_id(region, player_id):
    """Lấy thông tin chi tiết 1 player theo player_id để double-check GuildId."""
    base = REGION_API_BASE.get(region)
    if not base or not player_id:
        return None
    url = f"{base}/players/{player_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[albion_get_player_by_id] Lỗi: {e}")
        return None


# ==============================================================================
# REGISTRY HELPERS — đọc/ghi bảng member_registry trên Supabase
# ==============================================================================

async def registry_get(discord_id: str):
    """Lấy bản ghi registry của 1 user Discord. Trả None nếu chưa có."""
    row, err = await async_execute(
        lambda c: c.table("member_registry").select("*").eq("discord_id", str(discord_id)).maybe_single()
    )
    if err:
        return None
    return row.data if row and hasattr(row, "data") else None


async def registry_upsert(discord_id: str, player_id: str, ign: str, region: str, registered_by: str = None):
    """Lưu hoặc cập nhật registry entry."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "discord_id": str(discord_id),
        "player_id": str(player_id),
        "ign": ign,
        "region": region,
        "registered_by": str(registered_by) if registered_by else None,
        "updated_at": now,
    }
    _, err = await async_execute(
        lambda c: c.table("member_registry").upsert(row, on_conflict="discord_id")
    )
    return err


async def registry_delete(discord_id: str):
    """Xóa registry entry của 1 user Discord."""
    _, err = await async_execute(
        lambda c: c.table("member_registry").delete().eq("discord_id", str(discord_id))
    )
    return err


async def registry_get_all():
    """Lấy toàn bộ danh sách registry. Trả list (có thể rỗng)."""
    rows, err = await async_execute(
        lambda c: c.table("member_registry").select("*").order("ign")
    )
    if err or rows is None:
        return []
    return rows.data if hasattr(rows, "data") else []


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
        self._config_lock = asyncio.Lock()
        self._watch_lock = asyncio.Lock()
        # Bộ đếm vắng mặt liên tiếp: {player_id: missing_count}
        # Chỉ xử lý out guild khi vắng mặt liên tục ít nhất REQUIRED_MISSING_CYCLES lần (15 phút)
        self._missing_counts = {}
        self.REQUIRED_MISSING_CYCLES = 3

    async def cog_load(self):
        self.guild_leave_watcher.start()

    def cog_unload(self):
        self.guild_leave_watcher.cancel()

    # --------------------------------------------------------------------------
    # TASK NỀN: Phát hiện thành viên out guild & tự động gỡ role
    # --------------------------------------------------------------------------
    @tasks.loop(minutes=5)
    async def guild_leave_watcher(self):
        if self._watch_lock.locked():
            return
        async with self._watch_lock:
            await self._run_leave_watcher()

    @guild_leave_watcher.before_loop
    async def before_guild_leave_watcher(self):
        await self.bot.wait_until_ready()

    async def _run_leave_watcher(self):
        try:
            config = await load_guildcheck_config()
        except Exception as e:
            print(f"[guild_leave_watcher] Lỗi đọc config: {e}")
            return

        if not config.get("auto_strip_enabled"):
            return
        guild_id_albion = config.get("guild_id", "").strip()
        region = config.get("region", "Asia")
        log_channel_id = config.get("log_channel_id", "")
        guest_role_id = config.get("guest_role_id", "")
        if not guild_id_albion:
            return

        discord_guild = self.bot.get_guild(int(GUILD_ID))
        if not discord_guild:
            return

        # 1. Lấy danh sách thành viên từ Albion API
        members_raw = await albion_get_guild_members(region, guild_id_albion)
        if members_raw is None:
            print("[guild_leave_watcher] API Albion lỗi, bỏ qua chu kỳ này.")
            return

        curr_members = {
            m["Id"]: m["Name"]
            for m in members_raw
            if m.get("Id") and m.get("Name")
        }

        # 2. Load snapshot cũ
        try:
            snapshot = await load_guildcheck_snapshot()
        except Exception as e:
            print(f"[guild_leave_watcher] Lỗi đọc snapshot: {e}")
            return

        prev_members = snapshot.get("members", {})
        snap_guild_id = snapshot.get("guild_id", "")
        snap_region = snapshot.get("region", "")

        # Lần đầu hoặc đổi guild/region → chỉ lưu baseline, không gỡ role
        if not prev_members or snap_guild_id != guild_id_albion or snap_region != region:
            new_snap = {
                "guild_id": guild_id_albion,
                "region": region,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "members": curr_members,
            }
            try:
                await save_guildcheck_snapshot(new_snap)
            except Exception as e:
                print(f"[guild_leave_watcher] Lỗi lưu baseline snapshot: {e}")
            return

        # 3. Tìm missing player_id
        missing_ids = set(prev_members.keys()) - set(curr_members.keys())

        # Reset bộ đếm missing cho những người vẫn còn hoặc vừa xuất hiện lại
        for pid in list(self._missing_counts.keys()):
            if pid in curr_members:
                del self._missing_counts[pid]

        if not missing_ids:
            # Cập nhật snapshot nếu có người mới vào (ngược lại không gỡ ai)
            new_snap = {
                "guild_id": guild_id_albion,
                "region": region,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "members": curr_members,
            }
            try:
                await save_guildcheck_snapshot(new_snap)
            except Exception as e:
                print(f"[guild_leave_watcher] Lỗi lưu snapshot: {e}")
            return

        # 4. Circuit breaker: API trả thiếu hàng loạt → không gỡ role
        if len(prev_members) >= 10:
            threshold = max(15, int(len(prev_members) * 0.3))
            if len(missing_ids) >= threshold:
                print(f"[guild_leave_watcher] ⚠️ Circuit breaker: {len(missing_ids)} người biến mất cùng lúc, nghi API lag.")
                await self._send_log(discord_guild, log_channel_id, discord.Embed(
                    title="⚠️ Cảnh báo: Bot tạm dừng tự động gỡ role",
                    description=(
                        f"Phát hiện **{len(missing_ids)}** thành viên biến mất khỏi danh sách guild cùng lúc "
                        f"(ngưỡng an toàn: {threshold}).\n"
                        "Có thể API Albion đang trả thiếu dữ liệu. Bot **không gỡ role** lần này.\n"
                        "Nếu đây là thật, dùng `/guildaudit` để kiểm tra thủ công."
                    ),
                    color=0xe74c3c
                ))
                return

        # 5. Double-check từng player và gỡ role nếu xác nhận out guild
        next_members = dict(curr_members)  # sẽ bổ sung những người cần giữ lại

        for player_id in missing_ids:
            ign = prev_members.get(player_id, player_id)

            # Tăng bộ đếm vắng mặt liên tiếp
            count = self._missing_counts.get(player_id, 0) + 1
            self._missing_counts[player_id] = count

            # Nếu chưa đủ 3 lần vắng mặt liên tiếp (chưa đủ 15 phút) -> giữ lại snapshot, chưa gỡ
            if count < self.REQUIRED_MISSING_CYCLES:
                next_members[player_id] = ign
                print(f"[guild_leave_watcher] {ign} ({player_id}) vắng mặt {count}/{self.REQUIRED_MISSING_CYCLES} lần. Giữ lại theo dõi tiếp.")
                continue

            await asyncio.sleep(0.5)  # tránh spam API

            # Double-check qua API cá nhân
            player_info = await albion_get_player_by_id(region, player_id)
            if player_info is None:
                # API lỗi tạm thời → giữ lại trong snapshot, kiểm tra chu kỳ sau
                next_members[player_id] = ign
                print(f"[guild_leave_watcher] API lỗi khi check {ign}, giữ lại snapshot.")
                continue

            if player_info.get("GuildId") == guild_id_albion:
                # Vẫn còn trong guild (API danh sách bị cache thiếu) → giữ lại
                next_members[player_id] = ign
                self._missing_counts.pop(player_id, None)
                continue

            # Fallback an toàn lần 2: Search API theo tên nhân vật (search cập nhật nhanh hơn player endpoint)
            search_res = await albion_search_player(region, ign)
            if search_res and search_res.get("GuildId") == guild_id_albion:
                next_members[player_id] = ign
                self._missing_counts.pop(player_id, None)
                print(f"[guild_leave_watcher] {ign} search API vẫn còn guild TNC, giữ lại snapshot.")
                continue

            # Xác nhận đã out guild liên tiếp qua cả 3 vòng kiểm tra → xử lý Discord
            self._missing_counts.pop(player_id, None)
            current_guild_name = player_info.get("GuildName") or "Không có guild"
            await self._strip_roles(discord_guild, player_id, ign, current_guild_name, guest_role_id, log_channel_id)

        # 6. Lưu snapshot đã cập nhật
        new_snap = {
            "guild_id": guild_id_albion,
            "region": region,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "members": next_members,
        }
        try:
            await save_guildcheck_snapshot(new_snap)
        except Exception as e:
            print(f"[guild_leave_watcher] Lỗi lưu snapshot sau xử lý: {e}")

    async def _strip_roles(self, discord_guild: discord.Guild, player_id: str, ign: str, current_guild_name: str, guest_role_id: str, log_channel_id: str):
        """Tìm Discord member theo registry ĐÃ XÁC THỰC, gỡ toàn bộ role hợp lệ, gán guest_role, gửi log."""
        discord_member = None
        reg_discord_id = None

        rows, err = await async_execute(
            lambda c: c.table("member_registry").select("discord_id").eq("player_id", player_id).maybe_single()
        )
        if not err and rows and hasattr(rows, "data") and rows.data:
            reg_discord_id = rows.data.get("discord_id")
            if reg_discord_id:
                try:
                    discord_member = discord_guild.get_member(int(reg_discord_id)) or await discord_guild.fetch_member(int(reg_discord_id))
                except Exception:
                    discord_member = None

        # CHỈ GỠ ROLE KHI CÓ LIÊN KẾT XÁC THỰC TRONG member_registry!
        # Tuyệt đối KHÔNG fallback đoán mò theo nickname để tránh gỡ nhầm người chưa liên kết.
        if not discord_member or not reg_discord_id:
            print(f"[guild_leave_watcher] Bỏ qua {ign} ({player_id}): Chưa liên kết trong member_registry.")
            return

        bot_top_role = discord_guild.me.top_role
        removed_roles = []
        notes = []

        if discord_member:
            # Lọc role có thể gỡ
            removable = [
                r for r in discord_member.roles
                if r != discord_guild.default_role
                and not r.managed
                and r < bot_top_role
                and str(r.id) != str(guest_role_id)
            ]
            if removable:
                try:
                    await discord_member.remove_roles(*removable, reason=f"Tự động gỡ role: {ign} đã rời guild in-game")
                    removed_roles = [r.name for r in removable]
                except Exception as e:
                    notes.append(f"⚠️ Lỗi gỡ role: `{e}`")

            # Gán guest_role nếu có cấu hình
            if guest_role_id and str(guest_role_id).isdigit():
                guest_role = discord_guild.get_role(int(guest_role_id))
                if guest_role and guest_role < bot_top_role and guest_role not in discord_member.roles:
                    try:
                        await discord_member.add_roles(guest_role, reason=f"Gán role mặc định sau khi {ign} rời guild")
                    except Exception as e:
                        notes.append(f"⚠️ Lỗi gán role khách: `{e}`")

            # Xóa registry entry sau khi strip
            if reg_discord_id:
                await registry_delete(reg_discord_id)

        # Tạo embed log
        embed = discord.Embed(
            title="🚨 Phát hiện thành viên rời guild in-game",
            color=0xe74c3c,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🎮 IGN", value=f"`{ign}`", inline=True)
        embed.add_field(name="🏰 Guild hiện tại (game)", value=f"`{current_guild_name}`", inline=True)
        if discord_member:
            embed.add_field(name="💬 Discord", value=discord_member.mention, inline=True)
            embed.add_field(
                name="🗑️ Role đã gỡ",
                value=", ".join(f"`{r}`" for r in removed_roles) if removed_roles else "_(không có role nào cần gỡ)_",
                inline=False,
            )
            if guest_role_id and str(guest_role_id).isdigit():
                guest_role = discord_guild.get_role(int(guest_role_id))
                embed.add_field(name="🏷️ Role mặc định gán lại", value=f"`{guest_role.name}`" if guest_role else "`(không tìm thấy role)`", inline=True)
        else:
            embed.add_field(name="💬 Discord", value="❓ Không tìm thấy nick khớp trên server", inline=True)

        if notes:
            embed.add_field(name="⚠️ Ghi chú", value="\n".join(notes), inline=False)

        embed.set_footer(text="Tự động gỡ role bởi GuildCheck • Albion Online API")
        await self._send_log(discord_guild, log_channel_id, embed)

    async def _send_log(self, discord_guild: discord.Guild, log_channel_id: str, embed: discord.Embed):
        if not log_channel_id or not str(log_channel_id).isdigit():
            return
        channel = discord_guild.get_channel(int(log_channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[guild_leave_watcher] Lỗi gửi log: {e}")

    # --------------------------------------------------------------------------
    # LỆNH /guildconfig
    # --------------------------------------------------------------------------
    @app_commands.command(name="guildconfig", description="Cấu hình GuildCheck & tính năng tự động gỡ role (Officer only)")
    @app_commands.describe(
        guild_id="Guild ID Albion (lấy từ URL killboard guild)",
        region="Khu vực máy chủ (Asia, Americas, Europe)",
        auto_strip="Bật/tắt tự động gỡ role khi thành viên rời guild in-game",
        log_channel="Kênh nhận thông báo khi bot tự động gỡ role",
        guest_role="Role mặc định gán lại sau khi gỡ hết role guild (vd: Khách)",
        clear_guest_role="Xóa cấu hình role mặc định (gỡ trắng hoàn toàn)",
    )
    @app_commands.choices(region=[
        app_commands.Choice(name="Châu Á (East)", value="Asia"),
        app_commands.Choice(name="Châu Mỹ (West)", value="Americas"),
        app_commands.Choice(name="Châu Âu (EU)", value="Europe"),
    ])
    async def guildconfig_cmd(
        self,
        interaction: discord.Interaction,
        guild_id: str = None,
        region: app_commands.Choice[str] = None,
        auto_strip: bool = None,
        log_channel: discord.TextChannel = None,
        guest_role: discord.Role = None,
        clear_guest_role: bool = None,
    ):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            async with self._config_lock:
                config = await load_guildcheck_config()
                if guild_id:
                    config["guild_id"] = guild_id.strip()
                if region:
                    config["region"] = region.value
                if auto_strip is not None:
                    config["auto_strip_enabled"] = auto_strip
                if log_channel:
                    config["log_channel_id"] = str(log_channel.id)
                if guest_role:
                    config["guest_role_id"] = str(guest_role.id)
                if clear_guest_role:
                    config["guest_role_id"] = ""
                await save_guildcheck_config(config)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể cập nhật cấu hình GuildCheck: `{error}`", ephemeral=True)

        # Kiểm tra quyền manage_roles của bot
        bot_member = getattr(interaction.guild, "me", None)
        role_warning = ""
        if bot_member and not bot_member.guild_permissions.manage_roles:
            role_warning = "\n\n⚠️ **Bot chưa có quyền `Manage Roles`!** Vui lòng cấp quyền này để bot có thể tự động gỡ role."

        guest_role_obj = None
        if config.get("guest_role_id") and str(config.get("guest_role_id", "")).isdigit() and hasattr(interaction.guild, "get_role"):
            guest_role_obj = interaction.guild.get_role(int(config["guest_role_id"]))

        log_channel_obj = None
        if config.get("log_channel_id") and str(config.get("log_channel_id", "")).isdigit() and hasattr(interaction.guild, "get_channel"):
            log_channel_obj = interaction.guild.get_channel(int(config["log_channel_id"]))

        lines = [
            f"🆔 **Guild ID:** `{config.get('guild_id') or 'chưa cấu hình'}`",
            f"🌍 **Region:** `{config.get('region') or 'Asia'}`",
            f"🤖 **Tự động gỡ role:** `{'✅ Bật' if config.get('auto_strip_enabled') else '❌ Tắt'}`",
            f"📢 **Kênh log:** {log_channel_obj.mention if log_channel_obj else '`chưa cấu hình`'}",
            f"🏷️ **Role mặc định (Khách):** {guest_role_obj.mention if guest_role_obj else '`chưa cấu hình`'}",
        ]
        await interaction.edit_original_response(content="✅ **Cấu hình GuildCheck hiện tại:**\n" + "\n".join(lines) + role_warning)

    # --------------------------------------------------------------------------
    # LỆNH /guildcheck
    # --------------------------------------------------------------------------
    @app_commands.command(name="guildcheck", description="Tra cứu xem một thành viên có ở trong Guild hay không")
    @app_commands.describe(ign="Tên nhân vật trong game (chính xác)")
    async def guildcheck_cmd(self, interaction: discord.Interaction, ign: str):
        await interaction.response.defer(ephemeral=False)
        try:
            config = await load_guildcheck_config()
        except Exception as error:
            return await interaction.followup.send(
                f"❌ Không thể đọc cấu hình GuildCheck: `{error}`", ephemeral=True
            )
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")
        if not guild_id:
            return await interaction.followup.send(
                "❌ Chưa cấu hình Guild ID! Vui lòng nhờ Officer dùng `/guildconfig`.",
                ephemeral=True,
            )

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

    # --------------------------------------------------------------------------
    # LỆNH /registertnc
    # --------------------------------------------------------------------------
    @app_commands.command(name="registertnc", description="Đăng ký IGN Albion với tài khoản Discord")
    @app_commands.describe(
        region="Khu vực server Albion của bạn",
        ign="Tên nhân vật trong game (chính xác, phân biệt hoa/thường)",
        target="[Officer] Đăng ký thay cho thành viên khác",
    )
    @app_commands.choices(region=[
        app_commands.Choice(name="Châu Á (Asia)", value="Asia"),
        app_commands.Choice(name="Châu Mỹ (Americas)", value="Americas"),
        app_commands.Choice(name="Châu Âu (Europe)", value="Europe"),
    ])
    async def registertnc_cmd(
        self,
        interaction: discord.Interaction,
        region: app_commands.Choice[str],
        ign: str,
        target: discord.Member = None,
    ):
        # Nếu có target → chỉ Officer mới dùng được
        if target and not is_officer(interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ Officer mới có thể đăng ký thay cho người khác!", ephemeral=True
            )

        registrant = target or interaction.user
        await interaction.response.defer(ephemeral=False)

        # 1. Lấy guild_id Albion từ config
        try:
            config = await load_guildcheck_config()
        except Exception as e:
            return await interaction.followup.send(f"❌ Không thể đọc cấu hình: `{e}`", ephemeral=False)

        guild_id_albion = config.get("guild_id", "").strip()
        if not guild_id_albion:
            return await interaction.followup.send(
                "❌ Chưa cấu hình Guild ID! Nhờ Officer dùng `/guildconfig` trước.", ephemeral=False
            )

        # 2. Tìm player trên Albion API
        player = await albion_search_player(region.value, ign.strip())
        if player is None:
            return await interaction.followup.send(
                f"❌ Không tìm thấy nhân vật **`{ign}`** trên khu vực **{region.name}**.\n"
                "Kiểm tra lại chính tả hoặc chọn đúng khu vực server nhé.",
                ephemeral=False,
            )

        # 3. Kiểm tra có trong guild TNC không
        player_guild_id = player.get("GuildId", "")
        player_guild_name = player.get("GuildName") or "Không có guild"
        if player_guild_id != guild_id_albion:
            return await interaction.followup.send(
                f"❌ Nhân vật **`{player.get('Name')}`** hiện **không ở trong guild TNC**.\n"
                f"Guild hiện tại trong game: `{player_guild_name}`\n\n"
                "Chỉ thành viên đang trong guild TNC mới được đăng ký.",
                ephemeral=False,
            )

        # 4. Kiểm tra player_id chưa được đăng ký bởi người khác
        existing_by_pid, _ = await async_execute(
            lambda c: c.table("member_registry")
                .select("discord_id, ign")
                .eq("player_id", player["Id"])
                .maybe_single()
        )
        existing_by_pid_data = existing_by_pid.data if existing_by_pid and hasattr(existing_by_pid, "data") else None
        if existing_by_pid_data and str(existing_by_pid_data.get("discord_id")) != str(registrant.id):
            other_id = existing_by_pid_data.get("discord_id")
            return await interaction.followup.send(
                f"❌ IGN **`{player.get('Name')}`** đã được đăng ký bởi <@{other_id}>.\n"
                "Nếu có nhầm lẫn, nhờ Officer dùng `/unregistertnc` để xóa.",
                ephemeral=False,
            )

        # 5. Lưu vào member_registry
        err = await registry_upsert(
            discord_id=str(registrant.id),
            player_id=player["Id"],
            ign=player.get("Name", ign.strip()),
            region=region.value,
            registered_by=str(interaction.user.id) if target else None,
        )
        if err:
            return await interaction.followup.send(
                f"❌ Lỗi khi lưu đăng ký vào database: `{err}`", ephemeral=False
            )

        embed = discord.Embed(
            title="✅ Đăng Ký Thành Công!",
            color=0x2ecc71,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🎮 IGN", value=f"`{player.get('Name')}`", inline=True)
        embed.add_field(name="🌍 Region", value=f"`{region.name}`", inline=True)
        embed.add_field(name="🏰 Guild In-Game", value=f"`{player_guild_name}`", inline=True)
        if target:
            embed.add_field(name="👤 Đăng ký cho", value=registrant.mention, inline=True)
            embed.add_field(name="📝 Officer", value=interaction.user.mention, inline=True)
        else:
            embed.add_field(name="💬 Discord", value=registrant.mention, inline=True)
        embed.set_footer(text="Bot sẽ tự động gỡ role khi bạn rời guild TNC in-game.")
        await interaction.followup.send(embed=embed, ephemeral=False)

    # --------------------------------------------------------------------------
    # LỆNH /unregistertnc
    # --------------------------------------------------------------------------
    @app_commands.command(name="unregistertnc", description="Xóa đăng ký IGN Albion")
    @app_commands.describe(target="[Officer] Xóa đăng ký của thành viên khác (mặc định: xóa của chính bạn)")
    async def unregistertnc_cmd(self, interaction: discord.Interaction, target: discord.Member = None):
        if target and not is_officer(interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ Officer mới có thể xóa đăng ký của người khác!", ephemeral=True
            )
        registrant = target or interaction.user
        await interaction.response.defer(ephemeral=False)

        existing = await registry_get(str(registrant.id))
        if not existing:
            name_part = registrant.mention if target else "bạn"
            return await interaction.followup.send(
                f"❌ Không tìm thấy đăng ký nào của {name_part}.", ephemeral=False
            )

        err = await registry_delete(str(registrant.id))
        if err:
            return await interaction.followup.send(
                f"❌ Lỗi khi xóa đăng ký: `{err}`", ephemeral=False
            )

        ign = existing.get("ign", "?")
        await interaction.followup.send(
            f"✅ Đã xóa đăng ký **`{ign}`** của {registrant.mention}." if target
            else f"✅ Đã xóa đăng ký **`{ign}`** của bạn.",
            ephemeral=False,
        )

    # --------------------------------------------------------------------------
    # LỆNH /registerlist
    # --------------------------------------------------------------------------
    @app_commands.command(name="registerlist", description="Xem danh sách thành viên đã đăng ký IGN (Officer only)")
    async def registerlist_cmd(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền Officer!", ephemeral=True)
        await interaction.response.defer(ephemeral=False)

        rows = await registry_get_all()
        if not rows:
            return await interaction.followup.send("📭 Chưa có thành viên nào đăng ký IGN.", ephemeral=False)

        lines = []
        for i, row in enumerate(rows, 1):
            discord_id = row.get("discord_id", "?")
            ign = row.get("ign", "?")
            region = row.get("region", "?")
            registered_by = row.get("registered_by")
            by_part = f" _(Officer: <@{registered_by}>)_" if registered_by else ""
            lines.append(f"`{i:03d}` <@{discord_id}> → **{ign}** `[{region}]`{by_part}")

        # Phân trang đơn giản: gửi từng chunk 20 người
        chunk_size = 20
        chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
        for idx, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=f"📋 Danh Sách Đăng Ký IGN ({len(rows)} thành viên)",
                description="\n".join(chunk),
                color=0x3498db,
            )
            if len(chunks) > 1:
                embed.set_footer(text=f"Trang {idx + 1}/{len(chunks)}")
            await interaction.followup.send(embed=embed)

    # --------------------------------------------------------------------------
    # LỆNH /forcestrip
    # --------------------------------------------------------------------------
    @app_commands.command(
        name="forcestrip",
        description="Quét tổng thể in-game vs Discord, tự động gỡ role người đã out guild (Officer only)"
    )
    async def forcestrip_cmd(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền Officer!", ephemeral=True)

        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("❌ Lệnh này chỉ dùng trong server Discord!", ephemeral=False)

        try:
            config = await load_guildcheck_config()
        except Exception as e:
            return await interaction.followup.send(f"❌ Không thể đọc cấu hình: `{e}`", ephemeral=False)

        guild_id_albion = config.get("guild_id", "").strip()
        region = config.get("region", "Asia")
        guest_role_id = config.get("guest_role_id", "")
        log_channel_id = config.get("log_channel_id", "")

        if not guild_id_albion:
            return await interaction.followup.send(
                "❌ Chưa cấu hình Guild ID Albion! Dùng `/guildconfig` trước.", ephemeral=False
            )

        # 1. Lấy danh sách thành viên TNC in-game
        curr_members_raw = await albion_get_guild_members(region, guild_id_albion)
        if curr_members_raw is None:
            return await interaction.followup.send(
                "❌ Không thể kết nối tới Albion Online API. Vui lòng thử lại sau.", ephemeral=False
            )

        in_game_members = {m["Id"]: m.get("Name", "") for m in curr_members_raw if "Id" in m}

        # 2. Lấy toàn bộ danh sách đăng ký trong database
        registered = await registry_get_all()
        if not registered:
            return await interaction.followup.send(
                "📭 Chưa có thành viên nào trong danh sách đăng ký (`member_registry`).", ephemeral=False
            )

        stripped_list = []
        kept_count = 0
        api_error_count = 0

        # 3. Quét từng thành viên đã đăng ký
        for row in registered:
            player_id = row.get("player_id")
            ign = row.get("ign", "?")
            discord_id = row.get("discord_id")

            if not player_id:
                continue

            # Còn trong guild in-game
            if player_id in in_game_members:
                kept_count += 1
                continue

            # Không có trong danh sách in-game -> double check qua Player API
            await asyncio.sleep(0.4)
            p_info = await albion_get_player_by_id(region, player_id)
            if p_info is None:
                api_error_count += 1
                continue

            if p_info.get("GuildId") == guild_id_albion:
                kept_count += 1
                continue

            # Fallback an toàn lần 2: Search API theo tên
            s_res = await albion_search_player(region, ign)
            if s_res and s_res.get("GuildId") == guild_id_albion:
                kept_count += 1
                continue

            # Xác nhận out guild -> gỡ role
            current_guild_name = p_info.get("GuildName") or "Không có guild"
            await self._strip_roles(guild, player_id, ign, current_guild_name, guest_role_id, log_channel_id)
            tag = f"<@{discord_id}>" if discord_id else ign
            stripped_list.append(f"{tag} (**{ign}** → `{current_guild_name}`)")

        # 4. Cập nhật lại snapshot mới nhất
        new_snap = {
            "guild_id": guild_id_albion,
            "region": region,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "members": in_game_members,
        }
        try:
            await save_guildcheck_snapshot(new_snap)
        except Exception as e:
            print(f"[forcestrip] Lỗi lưu snapshot: {e}")

        # 5. Gửi embed báo cáo kết quả
        embed = discord.Embed(
            title="⚡ Kết Quả Quét & Lọc Thành Viên Tổng Thể (/forcestrip)",
            color=0x2ecc71 if not stripped_list else 0xe67e22,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="📋 Tổng số đã đăng ký", value=f"`{len(registered)}`", inline=True)
        embed.add_field(name="🏰 Thành viên còn trong TNC", value=f"`{kept_count}`", inline=True)
        embed.add_field(name="🚨 Đã gỡ role (out guild)", value=f"`{len(stripped_list)}`", inline=True)

        if stripped_list:
            chunk = stripped_list[:25]
            more = f"\n_...và {len(stripped_list) - 25} người khác._" if len(stripped_list) > 25 else ""
            embed.add_field(name="🗑️ Danh sách đã xử lý", value="\n".join(chunk) + more, inline=False)
        else:
            embed.description = "✅ Tất cả thành viên đã đăng ký đều đang ở trong guild TNC in-game!"

        if api_error_count > 0:
            embed.set_footer(text=f"⚠️ Bỏ qua {api_error_count} người do API Albion tạm thời lỗi.")
        else:
            embed.set_footer(text=f"Thực hiện bởi Officer: {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=False)

    # --------------------------------------------------------------------------
    # LỆNH /guildmembers
    # --------------------------------------------------------------------------
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
        await interaction.response.defer(ephemeral=False)
        try:
            config = await load_guildcheck_config()
        except Exception as error:
            return await interaction.followup.send(
                f"❌ Không thể đọc cấu hình GuildCheck: `{error}`", ephemeral=True
            )
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")
        if not guild_id:
            return await interaction.followup.send(
                "❌ Chưa cấu hình Guild ID! Vui lòng nhờ Officer dùng `/guildconfig` để cài đặt.",
                ephemeral=True,
            )

        members = await albion_get_guild_members(region, guild_id)
        if members is None:
            return await interaction.followup.send(
                "❌ Không thể lấy dữ liệu thành viên từ Albion API. Vui lòng kiểm tra lại Guild ID hoặc thử lại sau.",
                ephemeral=True
            )

        if not members:
            return await interaction.followup.send("📭 Guild hiện tại chưa có thành viên nào trên hệ thống API.")

        guild_name = members[0].get("GuildName") or "TNC Guild"

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

    # --------------------------------------------------------------------------
    # LỆNH /guildaudit
    # --------------------------------------------------------------------------
    @app_commands.command(name="guildaudit", description="Đối soát chéo thành viên In-game vs Thành viên Discord (Officer only)")
    async def guildaudit_cmd(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền Officer để dùng lệnh này!", ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong server Discord.", ephemeral=True)

        await interaction.response.defer(ephemeral=False)
        try:
            config = await load_guildcheck_config()
        except Exception as error:
            return await interaction.followup.send(
                f"❌ Không thể đọc cấu hình GuildCheck: `{error}`", ephemeral=True
            )
        guild_id = config.get("guild_id")
        region = config.get("region", "Asia")
        if not guild_id:
            return await interaction.followup.send(
                "❌ Chưa cấu hình Guild ID! Vui lòng dùng `/guildconfig` trước.",
                ephemeral=True,
            )

        members = await albion_get_guild_members(region, guild_id)
        if members is None:
            return await interaction.followup.send("❌ Không thể lấy dữ liệu thành viên từ Albion API. Vui lòng thử lại sau.")

        guild_name = members[0].get("GuildName") if members else "TNC Guild"

        ingame_map = {}
        for m in members:
            ign = (m.get("Name") or "").strip()
            if ign:
                ingame_map[ign.lower()] = ign

        discord_users = {}
        for dm in guild.members:
            if dm.bot:
                continue
            disp = dm.display_name.strip()
            name_only = disp
            for sep in ["[", "]", "|", "(", ")"]:
                name_only = name_only.replace(sep, " ")
            tokens = [t.strip().lower() for t in name_only.split() if t.strip()]
            discord_users[dm.id] = {
                "member": dm,
                "display_name": disp,
                "tokens": tokens,
                "raw_lower": disp.lower()
            }

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

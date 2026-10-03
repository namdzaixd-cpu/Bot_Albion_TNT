import re
import aiohttp
import asyncio
from copy import deepcopy
import discord
from discord import app_commands
from discord.ext import commands

from core.config import GUILD_NAME, GUILD_TAG, GUILD_ID
from core.permissions import is_officer
from core.db import async_execute
from core.config_store import get_config_async, invalidate


class OnboardConfig:
    def __init__(self, data=None):
        self.guild_id = str(GUILD_ID)
        self.data = deepcopy(data) if data is not None else None

    async def load(self):
        data = await get_config_async(
            "guild_config",
            self.guild_id,
            default=lambda: {"guild_id": self.guild_id, "is_onboard_enabled": True},
        )
        self.data = data
        return data

    async def save(self, changed):
        current, error = await async_execute(
            lambda client: client.table("guild_config").select("guild_id").eq(
                "guild_id", self.guild_id
            ).maybe_single()
        )
        if error:
            raise RuntimeError(f"Không đọc được guild_config: {error}")
        if not current or not current.data:
            _, error = await async_execute(
                lambda client: client.table("guild_config").insert(
                    {"guild_id": self.guild_id, "is_onboard_enabled": True}
                )
            )
            if error:
                raise RuntimeError(f"Không thể khởi tạo guild_config: {error}")
        _, error = await async_execute(
            lambda client: client.table("guild_config").update(changed).eq("guild_id", self.guild_id)
        )
        if error:
            raise RuntimeError(f"Không thể lưu cấu hình Onboarding: {error}")
        invalidate("guild_config", self.guild_id)
        self.data = await get_config_async(
            "guild_config",
            self.guild_id,
            default=lambda: {"guild_id": self.guild_id, "is_onboard_enabled": True},
        )
        return self.data

    @property
    def is_enabled(self):
        return self.data.get("is_onboard_enabled", True) if self.data else True

    @property
    def apply_channel_id(self):
        return self.data.get("apply_channel_id") if self.data else None

    @property
    def member_role_id(self):
        return self.data.get("member_role_id") if self.data else None

    @property
    def officer_role_id(self):
        return self.data.get("officer_role_id") if self.data else None

    @property
    def rules_channel_id(self):
        return self.data.get("rules_channel_id") if self.data else None

    @property
    def chat_channel_id(self):
        return self.data.get("chat_channel_id") if self.data else None

    @property
    def question_channel_id(self):
        return self.data.get("question_channel_id") if self.data else None

def _format_yob(yob: str) -> str:
    """Format năm sinh cho nickname: 2005→2k5, 2000→2k, 1998→98. Giữ nguyên nếu không phải 4 số."""
    formatted = yob
    if formatted.isdigit():
        if len(formatted) == 4:
            if formatted.startswith("20"):
                suffix = int(formatted[2:])
                formatted = f"2k{suffix}" if suffix else "2k"
            elif formatted.startswith("19"):
                formatted = formatted[2:]
    return formatted

def application_marker(thread):
    return f"https://discord.com/channels/{thread.guild.id}/{thread.id}"


def is_application_report(message, thread):
    return any(embed.url == application_marker(thread) for embed in message.embeds)


def get_onboard_data(interaction: discord.Interaction):
    thread = interaction.message.channel
    target_user_id = thread.owner_id
    embed = interaction.message.embeds[0]
    title = embed.title or ""
    ign_name = title.split(":", 1)[-1].strip()
    footer = embed.footer.text if embed.footer else ""
    yob = ""
    if footer and "YOB:" in footer:
        for part in footer.split("|"):
            if "YOB:" in part:
                yob = part.split("YOB:", 1)[1].strip()
    return target_user_id, ign_name, yob, embed


def status_from_title(title):
    if title and title.startswith("⏳ Chờ duyệt:"):
        return "submitted"
    if title and title.startswith("✅ Đã duyệt:"):
        return "approved"
    if title and title.startswith("❌ Đã từ chối:"):
        return "rejected"
    return None

class RulesConfirmView(discord.ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Tôi đã đọc & Đồng ý Nội Quy", style=discord.ButtonStyle.primary, custom_id="onboard_rules_read")
    async def confirm_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        if interaction.user.id != target_user_id:
            await interaction.response.send_message("❌ Nút này chỉ dành cho người nộp đơn!", ephemeral=True)
            return
            
        msg_text = (
            f"👉 **<@{target_user_id}>: Vui lòng nộp đơn (apply) vào guild `{GUILD_NAME}` trong game.**\n"
            f"Sau khi nộp xong ingame, hãy bấm nút **Đã gửi apply ingame** bên dưới để gọi Officer vào duyệt nhé!"
        )
        
        embed.color = discord.Color.gold()
        view = ApplicantConfirmView(self.cog)
        await interaction.response.edit_message(content=msg_text, embed=embed, view=view)

class ApplicantConfirmView(discord.ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Đã gửi apply ingame", style=discord.ButtonStyle.green, custom_id="onboard_applicant_done")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        if interaction.user.id != target_user_id:
            return await interaction.response.send_message("❌ Nút này chỉ dành cho người nộp đơn!", ephemeral=True)
        if embed.title.startswith(("⏳ Chờ duyệt:", "✅ Đã duyệt:", "❌ Đã từ chối:")):
            return await interaction.response.send_message("✅ Đơn này đã gửi Officer duyệt.", ephemeral=True)

        await interaction.response.defer()
        async with self.cog.application_lock(interaction.message.id):
            if interaction.message.id in self.cog.submitted_applications:
                return await interaction.followup.send("✅ Đơn này đã gửi Officer duyệt.", ephemeral=True)
            self.cog.submitted_applications.add(interaction.message.id)
            embed.color = discord.Color.orange()
            embed.title = f"⏳ Chờ duyệt: {ign_name}"
            view = OfficerApprovalView(self.cog)
            try:
                await interaction.message.edit(
                    content="⚠️ **Trạng thái:** Thành viên đã gửi đơn in-game. Mời Officer kiểm tra hòm thư và duyệt đơn bên dưới.",
                    embed=embed,
                    view=view,
                )
            except Exception:
                self.cog.submitted_applications.discard(interaction.message.id)
                raise
            self.cog.bot.add_view(view, message_id=interaction.message.id)
            officer_mention = f"<@&{self.cog.config.officer_role_id}>" if self.cog.config.officer_role_id else "@Officer"
            try:
                await interaction.channel.send(
                    f"🔔 {officer_mention}: Thành viên **{ign_name}** (<@{target_user_id}>) đã nộp đơn in-game! Vui lòng kiểm tra mail và duyệt đơn nhé."
                )
            except Exception as error:
                await interaction.followup.send(f"❌ Đơn đã gửi nhưng không thể ping Officer: `{error}`", ephemeral=True)

class OfficerApprovalView(discord.ui.View):
    def __init__(self, cog: 'Onboarding', status="submitted", renamed=False):
        super().__init__(timeout=None)
        self.cog = cog
        self.status = status
        self.renamed = renamed
        if status in {"approved", "rejected"}:
            for child in self.children:
                if child.custom_id in {"onboard_approve", "onboard_reject"}:
                    child.disabled = True
        if status == "rejected":
            for child in self.children:
                child.disabled = True
        if renamed:
            for child in self.children:
                if child.custom_id == "onboard_rename":
                    child.disabled = True

    async def _set_message_state(self, message, embed, status, ign_name, yob, *, content, actor):
        prefix = "✅ Đã duyệt" if status == "approved" else "❌ Đã từ chối"
        embed.title = f"{prefix}: {ign_name}"
        embed.color = discord.Color.green() if status == "approved" else discord.Color.red()
        footer = f"YOB: {yob} | {status.title()} bởi {actor}"
        if message.id in self.cog.renamed_applications:
            footer += " | Nickname đã đổi"
        embed.set_footer(text=footer)
        view = OfficerApprovalView(
            self.cog,
            status=status,
            renamed=message.id in self.cog.renamed_applications,
        )
        await message.edit(content=content, embed=embed, view=view)
        self.cog.application_states[message.id] = status
        self.cog.bot.add_view(view, message_id=message.id)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="onboard_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được duyệt!", ephemeral=True)
        await interaction.response.defer()
        message_id = interaction.message.id
        async with self.cog.application_lock(message_id):
            embed = interaction.message.embeds[0]
            state = self.cog.application_states.get(message_id, "submitted")
            if state != "submitted":
                return await interaction.followup.send("✅ Đơn này đã được xử lý.", ephemeral=True)
            target_user_id, ign_name, yob, _ = get_onboard_data(interaction)
            guild = interaction.guild
            member = guild.get_member(target_user_id) if guild else None
            if member:
                role_id = self.cog.config.member_role_id
                role = guild.get_role(int(role_id)) if role_id else None
                if not role_id:
                    await interaction.followup.send(
                        "⚠️ Chưa cài đặt Member Role nên bot không thể cấp role. Dùng `/recuibot setup_roles` để cài!",
                        ephemeral=True,
                    )
                elif not role:
                    await interaction.followup.send(
                        "⚠️ Role ID đã lưu không tồn tại. Dùng `/recuibot setup_roles` để cài lại!",
                        ephemeral=True,
                    )
                else:
                    try:
                        await member.add_roles(role)
                    except Exception as error:
                        await interaction.followup.send(f"⚠️ Không thể cấp role: `{error}`", ephemeral=True)
            else:
                await interaction.followup.send(
                    "⚠️ Không tìm thấy thành viên này trong server (có thể họ đã out).", ephemeral=True
                )

            message = interaction.message
            try:
                await self._set_message_state(
                    message,
                    embed,
                    "approved",
                    ign_name,
                    yob,
                    content=f"✅ Đơn apply của **{ign_name}** đã được duyệt bởi <@{interaction.user.id}>.",
                    actor=interaction.user.display_name,
                )
            except Exception as error:
                return await interaction.followup.send(f"❌ Không thể cập nhật trạng thái đơn: `{error}`", ephemeral=True)

            c_chat = f"<#{self.cog.config.chat_channel_id}>" if self.cog.config.chat_channel_id else "Kênh Guild-chat"
            c_question = f"<#{self.cog.config.question_channel_id}>" if self.cog.config.question_channel_id else "Kênh Hỏi đáp"
            welcome_msg = (
                f"🎉 Chào mừng <@{target_user_id}> đã gia nhập {GUILD_TAG}!\n\n"
                f"🔹 Ghé qua {c_chat} để đàm đạo, chém gió và giao lưu cùng anh em.\n"
                f"🔹 Bất cứ khi nào có thắc mắc hay cần hỗ trợ gì về game, bro cứ hét thẳng vào {c_question} nhé, mọi người sẽ giải đáp nhiệt tình.\n\n"
                "Khi vào guild hãy cư xử đúng mực, kính trên nhường dưới, không toxic và không gây war nha.\n"
                "Chúc bro chơi game vui vẻ ❤️"
            )
            try:
                await interaction.channel.send(welcome_msg)
            except Exception as error:
                await interaction.followup.send(f"❌ Đơn đã duyệt nhưng không thể gửi lời chào: `{error}`", ephemeral=True)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, custom_id="onboard_rename")
    async def rename_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được dùng!", ephemeral=True)
        member = interaction.guild.get_member(interaction.message.channel.owner_id) if interaction.guild else None
        if not member:
            return await interaction.response.send_message("❌ Không tìm thấy user này trong server (có thể họ đã out).", ephemeral=True)
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        new_nick = f"[{GUILD_TAG}] {ign_name} {_format_yob(yob)}".strip()[:32]
        await interaction.response.defer()
        async with self.cog.application_lock(interaction.message.id):
            if interaction.message.id in self.cog.renamed_applications:
                return await interaction.followup.send("✅ Nickname của đơn này đã được cập nhật.", ephemeral=True)
            try:
                await member.edit(nick=new_nick)
                footer = embed.footer.text if embed.footer else f"YOB: {yob}"
                embed.set_footer(text=f"{footer} | Nickname đã đổi")
                status = self.cog.application_states.get(interaction.message.id, "submitted")
                view = OfficerApprovalView(self.cog, status=status, renamed=True)
                await interaction.message.edit(embed=embed, view=view)
                self.cog.renamed_applications.add(interaction.message.id)
                self.cog.bot.add_view(view, message_id=interaction.message.id)
            except Exception as error:
                return await interaction.followup.send(f"❌ Không thể đổi nickname: `{error}`", ephemeral=True)
            await interaction.followup.send(f"✅ Đã tự động đổi tên thành `{new_nick}`!", ephemeral=False)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="onboard_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được duyệt!", ephemeral=True)
        await interaction.response.defer()
        message_id = interaction.message.id
        async with self.cog.application_lock(message_id):
            state = self.cog.application_states.get(message_id, "submitted")
            if state != "submitted":
                return await interaction.followup.send("✅ Đơn này đã được xử lý.", ephemeral=True)
            _, ign_name, yob, embed = get_onboard_data(interaction)
            try:
                await self._set_message_state(
                    interaction.message,
                    embed,
                    "rejected",
                    ign_name,
                    yob,
                    content=f"❌ Đơn apply của **{ign_name}** đã bị từ chối bởi <@{interaction.user.id}>.",
                    actor=interaction.user.display_name,
                )
            except Exception as error:
                await interaction.followup.send(f"❌ Không thể cập nhật trạng thái đơn: `{error}`", ephemeral=True)
class Onboarding(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = OnboardConfig()
        self.config_loaded = False
        self._application_locks = {}
        self.application_states = {}
        self.submitted_applications = set()
        self.renamed_applications = set()

    def application_lock(self, message_id):
        return self._application_locks.setdefault(message_id, asyncio.Lock())

    async def cog_load(self):
        try:
            await self.config.load()
            self.config_loaded = True
        except Exception as error:
            print(f"❌ Không thể tải cấu hình Onboarding: {error}")
            return

        self.bot.add_view(RulesConfirmView(self))
        self.bot.add_view(ApplicantConfirmView(self))
        forum_id = self.config.apply_channel_id
        forum = self.bot.get_channel(int(forum_id)) if forum_id else None
        if not isinstance(forum, discord.ForumChannel):
            return

        threads = {thread.id: thread for thread in forum.threads}
        try:
            async for thread in forum.archived_threads(limit=None):
                threads[thread.id] = thread
        except Exception as error:
            print(f"⚠️ Không tải được archived onboarding threads: {error}")

        for thread in threads.values():
            try:
                async for message in thread.history(limit=None):
                    if not is_application_report(message, thread):
                        continue
                    status = status_from_title(message.embeds[0].title)
                    if status:
                        self.application_states[message.id] = status
                        self.submitted_applications.add(message.id)
                        renamed = bool(
                            message.embeds[0].footer
                            and "Nickname đã đổi" in message.embeds[0].footer.text
                        )
                        if renamed:
                            self.renamed_applications.add(message.id)
                        self.bot.add_view(
                            OfficerApprovalView(self, status, renamed),
                            message_id=message.id,
                        )
            except Exception as error:
                print(f"⚠️ Không khôi phục được view onboarding cho thread {thread.id}: {error}")

    async def _save_config(self, changed):
        if not self.config_loaded:
            raise RuntimeError("Cấu hình Onboarding chưa tải được.")
        return await self.config.save(changed)

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
                    player_id = player["Id"]
                
                async with session.get(f"https://gameinfo-sgp.albiononline.com/api/gameinfo/players/{player_id}") as resp:
                    if resp.status != 200: return None
                    return await resp.json()
        except Exception as e:
            print(f"[Error] {e}")
            return None

    def validate_form(self, content: str):
        keywords = ["ingame", "năm sinh", "giới tính", "quốc gia", "thời gian", "mic", "chơi pc", "mobile", "role", "guild", "mục đích", "quy định"]
        count = sum(1 for kw in keywords if kw in content.lower())
        return count >= 4  

    async def process_apply_thread(self, thread: discord.Thread, msg: discord.Message = None):
        async with self.application_lock(thread.id):
            try:
                async for message in thread.history(limit=None):
                    if is_application_report(message, thread):
                        return
            except discord.Forbidden:
                print(f"❌ LỖI QUYỀN: Bot không thể kiểm tra đơn hiện có trong {thread.parent.name}")
                return
            await self._process_apply_thread(thread, msg)

    async def _process_apply_thread(self, thread: discord.Thread, msg: discord.Message = None):
        try:
            if not msg:
                try:
                    async for m in thread.history(limit=5, oldest_first=True):
                        if m.author.id == thread.owner_id:
                            msg = m
                            break
                except discord.Forbidden:
                    print(f"❌ LỖI QUYỀN: Bot không có quyền 'Đọc Lịch sử Tin nhắn' trong kênh {thread.parent.name}")
                    return
                    
            if not msg:
                return
                
            content = msg.content
            
            ign_match = re.search(r'Ingame\s*[:\-]?\s*([a-zA-Z0-9_]+)', content, re.IGNORECASE)
            yob_match = re.search(r'Năm sinh\s*[:\-]?\s*([a-zA-Z0-9]+)', content, re.IGNORECASE)
            
            if not ign_match:
                if not self.validate_form(content): return 
                await thread.send("⚠️ Bot không tìm thấy mục `Ingame:` trong đơn. Hãy viết rõ form `Ingame : Tên` nhé!")
                return
                
            if not self.validate_form(content):
                await thread.send("⚠️ Bro điền thiếu form rồi kìa, hãy điền đầy đủ form mẫu nhé!")
                return
                
            has_image = False
            if msg.attachments:
                for att in msg.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        has_image = True
                        break
            if "http" in content.lower() and ("png" in content.lower() or "jpg" in content.lower() or "jpeg" in content.lower() or "discord" in content.lower()):
                has_image = True
                
            if not has_image:
                try:
                    async for m in thread.history(limit=10, oldest_first=True):
                        if m.author.id == thread.owner_id and (m.attachments or "http" in m.content):
                            has_image = True
                            break
                except discord.Forbidden:
                    print(f"❌ LỖI QUYỀN: Bot không có quyền 'Đọc Lịch sử Tin nhắn' trong kênh {thread.parent.name}")
                    return
    
            if not has_image:
                # Check if bot already asked for image to prevent spamming
                already_asked = False
                try:
                    async for m in thread.history(limit=10, oldest_first=True):
                        if m.author == self.bot.user and "xin thêm ảnh stat" in m.content.lower():
                            already_asked = True
                            break
                except discord.Forbidden:
                    pass
                
                if not already_asked:
                    try:
                        await thread.send("Bro ơi cho tui xin thêm ảnh stat ingame nhé.")
                    except discord.Forbidden:
                        print(f"❌ LỖI QUYỀN: Bot không có quyền 'Gửi Tin nhắn trong Chuỗi' ở kênh {thread.parent.name}")
                return
                
            ign = ign_match.group(1).strip()
            yob = yob_match.group(1).strip() if yob_match else ""

            api_data = await self.fetch_albion_player(ign)
            if not api_data:
                await thread.send(f"❌ Không tìm thấy nhân vật `{ign}` trên hệ thống Albion. Officer vui lòng kiểm tra thủ công.")
                return
                
            embed = discord.Embed(title=f"Báo cáo tự động: {api_data.get('Name')}", color=discord.Color.blue())
            
            stats = api_data.get('LifetimeStatistics', {})
            pve_fame = stats.get('PvE', {}).get('Total', 0)
            gathering_fame = stats.get('Gathering', {}).get('All', {}).get('Total', 0)
            crafting_fame = stats.get('Crafting', {}).get('Total', 0)
            fishing_fame = stats.get('FishingFame', 0)
            farming_fame = stats.get('FarmingFame', 0)
            kill_fame = api_data.get('KillFame', 0)
            death_fame = api_data.get('DeathFame', 0)
            
            total_fame = pve_fame + gathering_fame + crafting_fame + fishing_fame + farming_fame + kill_fame
            
            embed.add_field(name="Total Fame", value=f"{total_fame:,}", inline=True)
            embed.add_field(name="PvE Fame", value=f"{pve_fame:,}", inline=True)
            embed.add_field(name="Kill Fame", value=f"{kill_fame:,}", inline=True)
            embed.add_field(name="Death Fame", value=f"{death_fame:,}", inline=True)
            
            old_guild = api_data.get('GuildName', 'Không có')
            embed.add_field(name="Guild Hiện Tại / Cũ", value=old_guild, inline=False)
            
            if yob:
                embed.set_footer(text=f"YOB: {yob}")
            
            embed.url = application_marker(thread)
            
            rules_channel = f"<#{self.config.rules_channel_id}>" if self.config.rules_channel_id else "Kênh Rules"
            msg_text = (
                f"⚠️ **<@{thread.owner_id}>: Vui lòng đọc thật kỹ nội quy tại {rules_channel} trước khi nộp đơn.**\n"
                f"Sau khi đã đọc và hiểu rõ nội quy, hãy bấm nút xác nhận bên dưới (Bắt buộc)."
            )
            await thread.send(content=msg_text, embed=embed, view=view)
        except Exception as e:
            print(f"❌ LỖI Onboarding: {e}")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.config_loaded or not self.config.is_enabled or message.author.bot:
            return
        if not isinstance(message.channel, discord.Thread):
            return
        apply_channel_id = self.config.apply_channel_id
        if not apply_channel_id or str(message.channel.parent_id) != str(apply_channel_id):
            return
        if message.author.id != message.channel.owner_id:
            return
        if message.id == message.channel.id or message.attachments or "http" in message.content:
            await self.process_apply_thread(
                message.channel,
                msg=message if message.id == message.channel.id else None,
            )

    @commands.Cog.listener()
    async def on_config_reload(self):
        invalidate("guild_config", self.config.guild_id)
        try:
            await self.config.load()
            self.config_loaded = True
        except Exception as error:
            self.config_loaded = False
            print(f"❌ Không thể tải lại cấu hình Onboarding: {error}")
    async def save_config_command(self, interaction, changed, success):
        if not self.config_loaded:
            return await interaction.response.send_message(
                "❌ Cấu hình Onboarding chưa tải được.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        try:
            await self._save_config(changed)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể lưu cấu hình: `{error}`", ephemeral=True)
        await interaction.edit_original_response(content=success)
    onboard_group = app_commands.Group(name="recuibot", description="Hệ thống Bot Thư Ký duyệt đơn")

    @onboard_group.command(name="toggle", description="Bật/Tắt chế độ Thư Ký tự động")
    async def onboard_toggle(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Ban quản trị mới được dùng!", ephemeral=True)
        enabled = not self.config.is_enabled
        status = "BẬT" if enabled else "TẮT"
        await self.save_config_command(
            interaction,
            {"is_onboard_enabled": enabled},
            f"✅ Đã **{status}** tính năng tự động check đơn thành viên mới.",
        )

    @onboard_group.command(name="set_apply_channel", description="Chỉ định kênh Forum dùng để nộp đơn")
    async def onboard_set_apply_channel(self, interaction: discord.Interaction, apply: discord.abc.GuildChannel):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)
        if not isinstance(apply, discord.ForumChannel):
            return await interaction.response.send_message(
                "❌ Kênh Apply bắt buộc phải là một **Kênh Diễn Đàn (Forum Channel)**! Vui lòng tạo một kênh Diễn đàn mới hoặc chọn đúng kênh Diễn đàn.",
                ephemeral=True,
            )
        await self.save_config_command(
            interaction,
            {"apply_channel_id": str(apply.id)},
            f"✅ Đã chỉ định kênh Apply thành công: <#{apply.id}>",
        )

    @onboard_group.command(name="setup_channels", description="Cài đặt các kênh cần thiết để bot tag trong lời chào")
    @app_commands.describe(
        rules_id="Copy ID của Kênh Rules và dán vào đây",
        guild_chat_id="Copy ID của Kênh Guild-chat và dán vào đây",
        question_id="Copy ID của Kênh Hỏi đáp và dán vào đây"
    )
    async def onboard_setup_channels(self, interaction: discord.Interaction,
                                     rules_id: str,
                                     guild_chat_id: str,
                                     question_id: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)

        def extract_id(value):
            match = re.search(r'\d+', value)
            return match.group(0) if match else value.strip()

        rules = extract_id(rules_id)
        chat = extract_id(guild_chat_id)
        question = extract_id(question_id)
        await self.save_config_command(
            interaction,
            {
                "rules_channel_id": rules,
                "chat_channel_id": chat,
                "question_channel_id": question,
            },
            f"✅ Đã lưu cấu hình kênh:\n- Rules: <#{rules}>\n- Chat: <#{chat}>\n- Q&A: <#{question}>",
        )

    @onboard_group.command(name="setup_roles", description="Cài đặt Role Officer và Role Member")
    async def onboard_setup_roles(self, interaction: discord.Interaction,
                                  officer_role: discord.Role,
                                  member_role: discord.Role):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)
        await self.save_config_command(
            interaction,
            {
                "officer_role_id": str(officer_role.id),
                "member_role_id": str(member_role.id),
            },
            "✅ Đã lưu cấu hình Role!",
        )

    @onboard_group.command(name="list", description="Xem cấu hình & trạng thái hệ thống Onboarding (Recuibot)")
    async def onboard_list(self, interaction: discord.Interaction):
        if not self.config_loaded:
            return await interaction.response.send_message(
                "❌ Không thể đọc cấu hình Onboarding. Vui lòng thử lại sau.",
                ephemeral=True,
            )
        data = self.config
        enabled = data.is_enabled
        apply_ch = data.apply_channel_id
        member_r = data.member_role_id
        officer_r = data.officer_role_id
        rules_ch = data.rules_channel_id
        chat_ch = data.chat_channel_id
        q_ch = data.question_channel_id

        embed = discord.Embed(title="⚙️ Cấu hình Onboarding (Recuibot)", color=0x3498db)
        embed.add_field(
            name="📌 Trạng thái & Kênh",
            value=(
                f"🔘 Bật/Tắt: **{'BẬT ✅' if enabled else 'TẮT ❌'}**\n"
                f"📨 Kênh nộp đơn: {f'<#{apply_ch}>' if apply_ch else '_Chưa cài_'}\n"
                f"📚 Kênh Rules: {f'<#{rules_ch}>' if rules_ch else '_Chưa cài_'}\n"
                f"💬 Kênh Chat: {f'<#{chat_ch}>' if chat_ch else '_Chưa cài_'}\n"
                f"❓ Kênh Q&A: {f'<#{q_ch}>' if q_ch else '_Chưa cài_'}"
            ),
            inline=False
        )
        embed.add_field(
            name="👥 Role",
            value=(
                f"🎖️ Officer: {f'<@&{officer_r}>' if officer_r else '_Chưa cài_'}\n"
                f"🛡️ Member: {f'<@&{member_r}>' if member_r else '_Chưa cài_'}"
            ),
            inline=False
        )

        if apply_ch:
            try:
                channel = interaction.guild.get_channel(int(apply_ch)) if interaction.guild else None
                if channel:
                    pending = 0
                    for thread in channel.threads:
                        if not thread.archived and thread.owner_id != self.bot.user.id:
                            pending += 1
                    embed.add_field(
                        name="📊 Đơn đang chờ duyệt",
                        value=f"**{pending}** đơn trong kênh nộp đơn",
                        inline=False
                    )
            except Exception as e:
                print(f"[onboarding-list] Lỗi đếm thread: {e}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))

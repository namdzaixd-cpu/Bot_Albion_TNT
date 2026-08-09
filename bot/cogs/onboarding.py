import os
import re
import aiohttp
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from core.config import STORAGE_DIR, GUILD_NAME, GUILD_TAG, GUILD_ID
from core.storage import load_json, save_json
from core.permissions import is_officer
from core.database import execute

class OnboardConfig:
    def __init__(self):
        self.guild_id = str(GUILD_ID)
        self.data = self._fetch_data()
        
    def _fetch_data(self):
        try:
            response, err = execute(lambda c: c.table("guild_config").select("*").eq("guild_id", self.guild_id))
            if err:
                print(f"Error fetching supabase config: {err}")
                return {"is_onboard_enabled": True}
            if response and response.data:
                return response.data[0]
            else:
                default_data = {"guild_id": self.guild_id, "is_onboard_enabled": True}
                _, err2 = execute(lambda c: c.table("guild_config").insert(default_data))
                if err2:
                    print(f"Error inserting default guild_config: {err2}")
                return default_data
        except Exception as e:
            print(f"Error fetching supabase config: {e}")
            return {"is_onboard_enabled": True}
            
    def save(self):
        try:
            update_data = {k: v for k, v in self.data.items() if k != "guild_id"}
            _, err = execute(lambda c: c.table("guild_config").update(update_data).eq("guild_id", self.guild_id))
            if err:
                print(f"Error saving supabase config: {err}")
        except Exception as e:
            print(f"Error saving supabase config: {e}")

    @property
    def is_enabled(self):
        return self.data.get("is_onboard_enabled", True)
        
    @is_enabled.setter
    def is_enabled(self, value: bool):
        self.data["is_onboard_enabled"] = value
        self.save()

    @property
    def apply_channel_id(self):
        return self.data.get("apply_channel_id")
        
    @property
    def member_role_id(self):
        return self.data.get("member_role_id")
        
    @property
    def officer_role_id(self):
        return self.data.get("officer_role_id")
        
    @property
    def rules_channel_id(self):
        return self.data.get("rules_channel_id")
        
    @property
    def chat_channel_id(self):
        return self.data.get("chat_channel_id")
        
    @property
    def question_channel_id(self):
        return self.data.get("question_channel_id")


def _format_yob(yob: str) -> str:
    """Format năm sinh cho nickname: 2005→2k5, 2000→2k, 1998→98. Giữ nguyên nếu không phải 4 số."""
    formatted = yob
    if formatted.isdigit():
        if len(formatted) == 4:
            if formatted.startswith("20"):
                formatted = f"2k{formatted[3:]}" if formatted[3:] != "0" else "2k"
            elif formatted.startswith("19"):
                formatted = formatted[2:]
    return formatted


def get_onboard_data(interaction: discord.Interaction):
    thread = interaction.message.channel
    target_user_id = thread.owner_id
    embed = interaction.message.embeds[0]
    title = embed.title
    if ":" in title:
        ign_name = title.split(":", 1)[1].strip()
    else:
        ign_name = title
        
    footer = embed.footer.text if embed.footer else ""
    yob = ""
    if footer and "YOB:" in footer:
        parts = footer.split("|")
        for part in parts:
            if "YOB:" in part:
                yob = part.split("YOB:")[1].strip()
    return target_user_id, ign_name, yob, embed

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
            
        await interaction.response.defer()
        
        msg_text = (
            f"👉 **<@{target_user_id}>: Vui lòng nộp đơn (apply) vào guild `{GUILD_NAME}` trong game.**\n"
            f"Sau khi nộp xong ingame, hãy bấm nút **Đã gửi apply ingame** bên dưới để gọi Officer vào duyệt nhé!"
        )
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        view = ApplicantConfirmView(self.cog)
        await interaction.channel.send(content=msg_text, embed=embed, view=view)

class ApplicantConfirmView(discord.ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Đã gửi apply ingame", style=discord.ButtonStyle.green, custom_id="onboard_applicant_done")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        if interaction.user.id != target_user_id:
            await interaction.response.send_message("❌ Nút này chỉ dành cho người nộp đơn!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        officer_mention = f"<@&{self.cog.config.officer_role_id}>" if self.cog.config.officer_role_id else "@Officer"
        msg_text = (
            f"✅ Thành viên mới đã xác nhận nộp đơn ingame. Mời {officer_mention} vào xem xét duyệt nhé!\n"
            "⚠️ **Lưu ý:** Thành viên đã xác nhận gửi apply ingame, Officer vui lòng kiểm tra mail apply và duyệt mail ingame trước khi bấm nút Accept"
        )
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        view = OfficerApprovalView(self.cog)
        await interaction.channel.send(content=msg_text, embed=embed, view=view)

    @discord.ui.button(label="Chưa gửi apply ingame", style=discord.ButtonStyle.secondary, custom_id="onboard_applicant_not_done")
    async def not_done(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        if interaction.user.id != target_user_id:
            await interaction.response.send_message("❌ Nút này chỉ dành cho người nộp đơn!", ephemeral=True)
            return
            
        await interaction.response.send_message(f"⚠️ Bạn vui lòng vào game, tìm guild **{GUILD_NAME}** và nộp đơn apply. Sau khi apply xong thì quay lại đây bấm nút **Đã gửi apply ingame** nhé!", ephemeral=False)

class OfficerApprovalView(discord.ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="onboard_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        from core.permissions import is_officer
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được duyệt!", ephemeral=True)
            return
            
        await interaction.response.defer()
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        guild = interaction.guild
        member = guild.get_member(target_user_id)
        if member:
            role_id = self.cog.config.member_role_id
            if not role_id:
                await interaction.followup.send("⚠️ Cảnh báo: Chưa cài đặt Member Role nên bot không thể cấp role. Dùng `/recuibot setup_roles` để cài!", ephemeral=False)
            else:
                role = guild.get_role(int(role_id))
                if not role:
                    await interaction.followup.send("⚠️ Cảnh báo: Role ID đã lưu không tồn tại (có thể role đã bị xóa). Dùng `/recuibot setup_roles` để cài lại!", ephemeral=False)
                else:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        await interaction.followup.send("⚠️ Cảnh báo: Bot không có quyền cấp Role này (Role của bot đang đứng thấp hơn Role cần cấp, hoặc bot thiếu quyền Manage Roles)!", ephemeral=False)
                    except Exception as e:
                        await interaction.followup.send(f"⚠️ Cảnh báo: Lỗi khi cấp role: {e}", ephemeral=False)
        else:
            await interaction.followup.send("⚠️ Cảnh báo: Không tìm thấy thành viên này trong server (có thể họ đã out).", ephemeral=False)
        
        for child in self.children:
            if child.custom_id in ["onboard_approve", "onboard_reject"]:
                child.disabled = True
            
        embed.color = discord.Color.green()
        embed.title = f"✅ Đã duyệt: {ign_name}"
        embed.set_footer(text=f"YOB: {yob} | Duyệt bởi {interaction.user.display_name}")
        await interaction.message.edit(embed=embed, view=self)
        
        c_rules = f"<#{self.cog.config.rules_channel_id}>" if self.cog.config.rules_channel_id else "Kênh Rules"
        c_chat = f"<#{self.cog.config.chat_channel_id}>" if self.cog.config.chat_channel_id else "Kênh Guild-chat"
        c_question = f"<#{self.cog.config.question_channel_id}>" if self.cog.config.question_channel_id else "Kênh Hỏi đáp"
        
        welcome_msg = (
            f"🎉 Chào mừng <@{target_user_id}> đã gia nhập {GUILD_TAG}!\n\n"
            f"🔹 Ghé qua {c_chat} để đàm đạo, chém gió và giao lưu cùng anh em.\n"
            f"🔹 Bất cứ khi nào có thắc mắc hay cần hỗ trợ gì về game, bro cứ hét thẳng vào {c_question} nhé, mọi người sẽ giải đáp nhiệt tình.\n\n"
            f"Khi vào guild hãy cư xử đúng mực, kính trên nhường dưới, không toxic và không gây war nha.\n"
            f"Chúc bro chơi game vui vẻ ❤️"
        )
        await interaction.channel.send(welcome_msg)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, custom_id="onboard_rename")
    async def rename_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        from core.permissions import is_officer
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được dùng!", ephemeral=True)
            return
            
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        guild = interaction.guild
        member = guild.get_member(target_user_id)
        if not member:
            await interaction.response.send_message("❌ Không tìm thấy user này trong server (có thể họ đã out).", ephemeral=True)
            return
            
        formatted_yob = _format_yob(yob)
        
        new_nick = f"[{GUILD_TAG}] {ign_name} {formatted_yob}".strip()
        if len(new_nick) > 32:
            new_nick = new_nick[:32]
            
        try:
            await member.edit(nick=new_nick)
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ Đã tự động đổi tên thành `{new_nick}`!", ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Lỗi quyền: Bot không có quyền đổi tên user này (có thể role của họ cao hơn bot hoặc bot chưa có quyền Manage Nicknames).", ephemeral=False)
        except Exception as e:
            await interaction.response.send_message(f"❌ Có lỗi xảy ra: {e}", ephemeral=False)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="onboard_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        from core.permissions import is_officer
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Officer trở lên mới được duyệt!", ephemeral=True)
            return
            
        await interaction.response.defer()
        target_user_id, ign_name, yob, embed = get_onboard_data(interaction)
        for child in self.children:
            child.disabled = True
            
        embed.color = discord.Color.red()
        embed.title = f"❌ Đã từ chối: {ign_name}"
        embed.set_footer(text=f"YOB: {yob} | Từ chối bởi {interaction.user.display_name}")
        await interaction.message.edit(embed=embed, view=self)

class Onboarding(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = OnboardConfig()

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
            
            view = RulesConfirmView(self)
            
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
        print(f"DEBUG Onboarding: on_message triggered. is_enabled: {self.config.is_enabled}")
        if not self.config.is_enabled: return
        if message.author.bot: return
        if not isinstance(message.channel, discord.Thread): return
        
        apply_ch = self.config.apply_channel_id
        if not apply_ch or str(message.channel.parent_id) != str(apply_ch):
            return
            
        print(f"DEBUG Onboarding: Nhận tin nhắn trong kênh apply {message.channel.name}")
        
        if message.author.id != message.channel.owner_id:
            print("DEBUG Onboarding: Người gửi không phải chủ thread, bỏ qua.")
            return
            
        # Nếu đây là tin nhắn gốc (starter message) của Thread, xử lý luôn
        if message.id == message.channel.id:
            print("DEBUG Onboarding: Tin nhắn gốc của Forum, xử lý process_apply_thread.")
            await self.process_apply_thread(message.channel, msg=message)
            return
            
        async for m in message.channel.history(limit=20):
            if m.author == self.bot.user and m.embeds and "Báo cáo tự động" in str(m.embeds[0].title):
                return
                
        if message.attachments or "http" in message.content:
            await self.process_apply_thread(message.channel)

    @commands.Cog.listener()
    async def on_config_reload(self):
        # Triggered by webhook to reload config from Supabase
        self.config = OnboardConfig()
        print("✅ Đã tự động cập nhật cấu hình Onboarding từ Dashboard!")
    onboard_group = app_commands.Group(name="recuibot", description="Hệ thống Bot Thư Ký duyệt đơn")

    @onboard_group.command(name="toggle", description="Bật/Tắt chế độ Thư Ký tự động")
    async def onboard_toggle(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Chỉ Ban quản trị mới được dùng!", ephemeral=True)
            return
        self.config.is_enabled = not self.config.is_enabled
        status = "BẬT" if self.config.is_enabled else "TẮT"
        await interaction.response.send_message(f"✅ Đã **{status}** tính năng tự động check đơn thành viên mới.", ephemeral=True)

    @onboard_group.command(name="set_apply_channel", description="Chỉ định kênh Forum dùng để nộp đơn")
    async def onboard_set_apply_channel(self, interaction: discord.Interaction, apply: discord.abc.GuildChannel):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)
            return
            
        if not isinstance(apply, discord.ForumChannel):
            await interaction.response.send_message("❌ Kênh Apply bắt buộc phải là một **Kênh Diễn Đàn (Forum Channel)**! Vui lòng tạo một kênh Diễn đàn mới hoặc chọn đúng kênh Diễn đàn.", ephemeral=True)
            return
        
        self.config.data["apply_channel_id"] = str(apply.id)
        self.config.save()
        await interaction.response.send_message(f"✅ Đã chỉ định kênh Apply thành công: <#{apply.id}>", ephemeral=True)

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
            await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)
            return
        
        def extract_id(val: str):
            import re
            m = re.search(r'\d+', val)
            return m.group(0) if m else val.strip()

        self.config.data["rules_channel_id"] = extract_id(rules_id)
        self.config.data["chat_channel_id"] = extract_id(guild_chat_id)
        self.config.data["question_channel_id"] = extract_id(question_id)
        self.config.save()
        
        await interaction.response.send_message(
            f"✅ Đã lưu cấu hình kênh:\n"
            f"- Rules: <#{self.config.data['rules_channel_id']}>\n"
            f"- Chat: <#{self.config.data['chat_channel_id']}>\n"
            f"- Q&A: <#{self.config.data['question_channel_id']}>", 
            ephemeral=True
        )

    @onboard_group.command(name="setup_roles", description="Cài đặt Role Officer và Role Member")
    async def onboard_setup_roles(self, interaction: discord.Interaction, 
                                  officer_role: discord.Role,
                                  member_role: discord.Role):
        if not is_officer(interaction.user):
            await interaction.response.send_message("❌ Xin lỗi, chỉ Ban quản trị mới được quyền chỉnh!", ephemeral=True)
            return
        
        self.config.data["officer_role_id"] = str(officer_role.id)
        self.config.data["member_role_id"] = str(member_role.id)
        self.config.save()
        await interaction.response.send_message(f"✅ Đã lưu cấu hình Role!", ephemeral=True)

    @onboard_group.command(name="list", description="Xem cấu hình & trạng thái hệ thống Onboarding (Recuibot)")
    async def onboard_list(self, interaction: discord.Interaction):
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
    cog = Onboarding(bot)
    await bot.add_cog(cog)
    bot.add_view(RulesConfirmView(cog))
    bot.add_view(ApplicantConfirmView(cog))
    bot.add_view(OfficerApprovalView(cog))

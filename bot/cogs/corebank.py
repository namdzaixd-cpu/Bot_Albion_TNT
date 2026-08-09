import os
import re
from datetime import datetime
import aiohttp

import discord
from discord import app_commands
from discord.ext import commands

from core.permissions import is_officer
from core.config_store import get_config, save_config, reload_all
from core.database import execute
from core.config import GUILD_ID

# ==============================================================================
# HỆ THỐNG CORE-BANK (Tích hợp UnbelievaBoat)
# ==============================================================================

def parse_emoji_input(emoji_str: str):
    """Phân tích chuỗi emoji từ lệnh slash.
    Trả về (key, display_str):
      - key: ID (custom emoji) hoặc ký tự unicode (emoji thường)
      - display_str: chuỗi hiển thị để bot in ra
    """
    emoji_str = emoji_str.strip()
    match = re.match(r'<a?:(\w+):(\d+)>', emoji_str)
    if match:
        name, eid = match.group(1), match.group(2)
        return eid, f"<:{name}:{eid}>"
    return emoji_str, emoji_str

def get_reaction_key(emoji) -> str:
    """Lấy key nhất quán cho emoji reaction (PartialEmoji)."""
    return str(emoji.id) if emoji.id else emoji.name

def _sorted_emoji_keys(emoji_map: dict) -> list:
    """Thứ tự emoji react: tăng dần theo (order, value). Dùng cho cả on_message
    (react bình thường + tách ảnh) — tách ra để test thứ tự dễ kiểm chứng."""
    return sorted(emoji_map.keys(), key=lambda k: (emoji_map[k].get("order", 0), emoji_map[k]["value"]))

class CoreBankCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = {}
        self._reload_config()

    def _reload_config(self):
        try:
            default_config = {
                "guild_id": str(GUILD_ID),
                "core_channel_id": "",
                "bank_channel_id": "",
                "unbelievaboat_token": "",
                "emoji_map": {},
                "auto_react": True,
            }
            data = get_config(
                "corebank_config", str(GUILD_ID), default=default_config
            )
            # Đảm bảo các trường thiếu có giá trị mặc định
            merged = {**default_config, **(data or {})}
            self.config = merged
        except Exception as e:
            print(f"⚠️ [Core-Bank] Lỗi khi load config: {e}")
            self.config = {
                "core_channel_id": "", "bank_channel_id": "",
                "unbelievaboat_token": "", "emoji_map": {}, "auto_react": True,
            }

    def _save_config(self):
        try:
            self.config["guild_id"] = str(GUILD_ID)
            save_config("corebank_config", self.config, on_conflict="guild_id")
        except Exception as e:
            print(f"⚠️ [Core-Bank] Lỗi khi save config: {e}")

    @commands.Cog.listener()
    async def on_config_reload(self):
        self._reload_config()
        print("✅ Đã cập nhật cấu hình CoreBank từ Dashboard!")

    # ── Tự động react vào ảnh trong kênh Core ───────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        try:
            core_config = self.config
            if core_config.get("auto_react", True):
                core_ch_id = core_config.get("core_channel_id")
                is_core = str(message.channel.id) == core_ch_id
                if not is_core and hasattr(message.channel, "parent_id"):
                    is_core = str(message.channel.parent_id) == core_ch_id
                
                if is_core:
                    if message.attachments:
                        emoji_map = core_config.get("emoji_map", {})

                    # Xử lý tách ảnh nếu có nhiều hơn 1 ảnh
                    if len(message.attachments) > 1:
                        await message.reply("🔄 Phát hiện nhiều ảnh, bot đang tách ra thành từng tin nhắn để dễ chấm điểm...")
                        for i, att in enumerate(message.attachments):
                            try:
                                file = await att.to_file()
                                text = f"📸 Ảnh tách ra từ {message.author.mention} (Ảnh {i+1}/{len(message.attachments)})"
                                if i == 0 and message.content:
                                    text += f"\n📝 Lời nhắn gốc: {message.content}"
                                split_msg = await message.channel.send(content=text, file=file)

                                # Tự động react vào ảnh tách ra
                                if emoji_map:
                                    sorted_keys = sorted(emoji_map.keys(), key=lambda k: (emoji_map[k].get("order", 0), emoji_map[k]["value"]))
                                    for key in sorted_keys:
                                        try:
                                            emoji_str = emoji_map[key]["display"]
                                            reaction = discord.PartialEmoji.from_str(emoji_str) if ":" in emoji_str else emoji_str
                                            await split_msg.add_reaction(reaction)
                                        except Exception as e:
                                            print(f"[Error] {e}")
                                            pass
                            except Exception as e:
                                print(f"⚠️ [Core-Bank] Lỗi khi tách ảnh: {e}")

                        # Xóa tin nhắn gốc sau khi đã tách thành công
                        try:
                            await message.delete()
                        except Exception as e:
                            print(f"[Error] {e}")
                            pass
                        return  # Đã tách ảnh xong, dừng xử lý tin nhắn gốc

                    # Nếu chỉ 1 ảnh thì react bình thường vào tin nhắn gốc
                    if emoji_map:
                        sorted_keys = sorted(emoji_map.keys(), key=lambda k: (emoji_map[k].get("order", 0), emoji_map[k]["value"]))
                        for key in sorted_keys:
                            try:
                                emoji_str = emoji_map[key]["display"]
                                reaction = discord.PartialEmoji.from_str(emoji_str) if ":" in emoji_str else emoji_str
                                await message.add_reaction(reaction)
                            except Exception as e:
                                print(f"[Error] {e}")
                                pass
        except Exception as e:
            print(f"⚠️ [Core-Bank] Lỗi khi tự động react: {e}")

    # ── Lệnh cấu hình ────────────────────────────────────────────────────────

    @app_commands.command(name="coresetup", description="Cài đặt kênh và API Token cho hệ thống Core-Bank (Officer only)")
    @app_commands.describe(
        core_channel="Kênh #core-vortex hoặc Diễn đàn nơi member đăng ảnh",
        bank_channel="Kênh bot gửi lệnh !add-money / !remove-money cho UnbelievaBoat",
        token="API Token lấy từ trang chủ UnbelievaBoat"
    )
    async def coresetup_cmd(self, interaction: discord.Interaction,
                             core_channel: discord.abc.GuildChannel,
                             bank_channel: discord.abc.GuildChannel,
                             token: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)
        self.config["core_channel_id"] = str(core_channel.id)
        self.config["bank_channel_id"] = str(bank_channel.id)
        self.config["unbelievaboat_token"] = token
        self._save_config()
        await interaction.response.send_message(
            f"✅ Đã cài đặt Core-Bank:\n"
            f"📸 Core channel: {core_channel.mention}\n"
            f"💰 Bank channel: {bank_channel.mention}\n"
            f"🔑 UnbelievaBoat Token: **Đã cài ✅**",
            ephemeral=True
        )

    @app_commands.command(name="coreadd", description="Thêm emoji Core (hỗ trợ nhiều cùng lúc, phân cách bằng dấu phẩy) (Officer only)")
    @app_commands.describe(
        emoji="Emoji đại diện, phân cách bằng phẩy (vd: 🟢,🔵 hoặc <:a:123>,<:b:456>)",
        name="Tên Core, phân cách bằng phẩy (vd: Green Core,Blue Core)",
        value="Giá trị silver, phân cách bằng phẩy (vd: 100000,200000)",
        order="Số thứ tự hiển thị, phân cách bằng phẩy (tùy chọn, mặc định 0)"
    )
    async def coreadd_cmd(self, interaction: discord.Interaction, emoji: str, name: str, value: str, order: str = ""):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)

        emojis = [e.strip() for e in emoji.split(",")]
        names  = [n.strip() for n in name.split(",")]
        values = [v.strip() for v in value.split(",")]
        orders = [o.strip() for o in order.split(",")] if order.strip() else []

        count = len(emojis)
        if len(names) != count or len(values) != count:
            return await interaction.response.send_message(
                "⚠️ Số lượng emoji, tên và giá trị phải bằng nhau!\n"
                "Ví dụ: `/coreadd 🟢,🔵 Green Core,Blue Core 100000,200000`",
                ephemeral=True
            )

        results, errors = [], []

        for i in range(count):
            try:
                v = int(values[i].replace(".", "").replace(",", ""))
                if v <= 0:
                    errors.append(f"❌ `{names[i]}`: giá trị phải > 0")
                    continue
                o = int(orders[i]) if i < len(orders) and orders[i] else 0
                key, display = parse_emoji_input(emojis[i])
                self.config.setdefault("emoji_map", {})[key] = {"name": names[i], "value": v, "display": display, "order": o}
                results.append(f"✅ {display} **{names[i]}** — {v:,} silver (STT: {o})")
            except ValueError:
                errors.append(f"❌ `{values[i]}`: giá trị không hợp lệ")

        if results:
            self._save_config()

        lines = results + errors
        msg = "\n".join(lines) if lines else "⚠️ Không có gì được thêm."
        await interaction.response.send_message(
            f"📋 Kết quả thêm Core ({len(results)}/{count} thành công):\n{msg}",
            ephemeral=True
        )

    @app_commands.command(name="coreremove", description="Xóa emoji Core khỏi danh sách (Officer only)")
    @app_commands.describe(emoji="Emoji muốn xóa")
    async def coreremove_cmd(self, interaction: discord.Interaction, emoji: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)
        key, display = parse_emoji_input(emoji)
        emoji_map = self.config.get("emoji_map", {})
        if key not in emoji_map:
            return await interaction.response.send_message(f"❓ Không tìm thấy emoji `{display}` trong danh sách.", ephemeral=True)
        removed = emoji_map.pop(key)
        self._save_config()
        await interaction.response.send_message(
            f"🗑️ Đã xóa: {display} = **{removed['name']}** ({removed['value']:,} silver)",
            ephemeral=True
        )

    @app_commands.command(name="coreautoreact", description="Bật/tắt tự động thả emoji vào ảnh trong kênh Core (Officer only)")
    @app_commands.describe(enable="Bật (True) hoặc Tắt (False)")
    async def coreautoreact_cmd(self, interaction: discord.Interaction, enable: bool):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)
        self.config["auto_react"] = enable
        self._save_config()
        state = "BẬT ✅" if enable else "TẮT ❌"
        await interaction.response.send_message(f"⚙️ Tự động thả emoji vào ảnh trong kênh Core: **{state}**", ephemeral=True)

    @app_commands.command(name="corelist", description="Xem danh sách emoji Core và cấu hình hiện tại")
    async def corelist_cmd(self, interaction: discord.Interaction):
        emoji_map = self.config.get("emoji_map", {})
        core_ch = self.config.get("core_channel_id")
        bank_ch = self.config.get("bank_channel_id")
        token = self.config.get("unbelievaboat_token", "")
        auto_react = self.config.get("auto_react", True)

        embed = discord.Embed(title="⚙️ Cấu hình Core-Bank", color=0xf1c40f)
        embed.add_field(
            name="📌 Kênh & Cấu hình",
            value=(f"📸 Core: {f'<#{core_ch}>' if core_ch else '_Chưa cài_'}\n"
                   f"💰 Bank: {f'<#{bank_ch}>' if bank_ch else '_Chưa cài_'}\n"
                   f"🔑 Token API: **{'Đã cài ✅' if token else 'Chưa cài ❌'}**\n"
                   f"🤖 Tự động react ảnh: **{'BẬT ✅' if auto_react else 'TẮT ❌'}**"),
            inline=False
        )
        if emoji_map:
            sorted_emojis = sorted(emoji_map.values(), key=lambda x: (x.get("order", 0), x["value"]))
            lines = [f"{info['display']} **{info['name']}** — {info['value']:,} silver (STT: {info.get('order', 0)})"
                     for info in sorted_emojis]
            embed.add_field(name=f"📋 Danh sách Core ({len(emoji_map)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📋 Danh sách Core", value="_Chưa có emoji nào. Dùng `/coreadd` để thêm._", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Event: Phát hiện react & gỡ react ───────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        core_ch_id = self.config.get("core_channel_id")
        bank_ch_id = self.config.get("bank_channel_id")
        emoji_map = self.config.get("emoji_map", {})

        # Chỉ xử lý trong kênh core đã cài hoặc thread thuộc kênh core
        if not core_ch_id:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        channel = guild.get_channel(payload.channel_id) or guild.get_thread(payload.channel_id)
        if not channel:
            try:
                channel = await guild.fetch_channel(payload.channel_id)
            except Exception as e:
                print(f"[Error] {e}")
                return
            
        is_core = str(payload.channel_id) == core_ch_id
        if not is_core and hasattr(channel, "parent_id"):
            is_core = str(channel.parent_id) == core_ch_id
            
        if not is_core:
            return

        emoji_key = get_reaction_key(payload.emoji)
        if emoji_key not in emoji_map:
            return

        reactor = guild.get_member(payload.user_id)
        if not reactor or not is_officer(reactor):
            return  # Không phải Officer → bỏ qua

        # Kiểm tra chống cộng trùng trong Supabase
        credit_key = f"{payload.message_id}:{emoji_key}"
        try:
            res, err = execute(lambda c: c.table("core_credited").select("*").eq("message_id", credit_key))
            if err:
                print(f"Lỗi truy vấn core_credited: {err}")
            elif res and res.data:
                return  # Đã cộng rồi, Officer khác react sau → bỏ qua
        except Exception as e:
            print(f"Lỗi truy vấn core_credited: {e}")
            pass

        # Lấy tin nhắn gốc để tìm ra member đã đăng ảnh
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception as e:
            print(f"[Error] {e}")
            return
        author = message.author

        # Xác định lại tác giả nếu đó là ảnh do bot tách ra
        if author.id == self.bot.user.id and "Ảnh tách ra từ <@" in message.content:
            match = re.search(r"Ảnh tách ra từ <@!?(\d+)>", message.content)
            if match:
                actual_id = match.group(1)
                actual_member = guild.get_member(int(actual_id))
                if actual_member:
                    author = actual_member

        if author.bot:
            return

        core_info = emoji_map[emoji_key]
        core_name = core_info["name"]
        core_value = core_info["value"]
        core_disp = core_info.get("display", emoji_key)

        # Lấy bank channel
        bank_channel = guild.get_channel(int(bank_ch_id)) if bank_ch_id else None
        if not bank_channel:
            await channel.send(
                "⚠️ Chưa cài bank channel! Dùng `/coresetup` trước.",
                reference=message
            )
            return

        # Ghi nhận trước vào Supabase để tránh race condition
        try:
            _, err = execute(lambda c: c.table("core_credited").insert({
                "message_id": credit_key,
                "user_id": str(reactor.id),  # Ở đây mình lưu người react để biết ai cộng
                "amount": core_value
            }))
            if err:
                print(f"Lỗi ghi core_credited: {err}")
        except Exception as e:
            print(f"Lỗi ghi core_credited: {e}")
            pass

        # Xử lý API UnbelievaBoat
        token = self.config.get("unbelievaboat_token")
        if not token:
            await channel.send("⚠️ Chưa cài UnbelievaBoat API Token! Hãy dùng `/coresetup`.", reference=message)
            return

        api_url = f"https://unbelievaboat.com/api/v1/guilds/{payload.guild_id}/users/{author.id}"
        headers = {"Authorization": token}
        payload_data = {"bank": core_value, "reason": f"CoreBank: {core_name}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(api_url, headers=headers, json=payload_data) as resp:
                    if resp.status not in (200, 204):
                        err_text = await resp.text()
                        await channel.send(f"⚠️ Lỗi API UnbelievaBoat ({resp.status}): {err_text}", reference=message)
                        return
        except Exception as e:
            await channel.send(f"⚠️ Lỗi kết nối API UnbelievaBoat: {e}", reference=message)
            return

        # Xác nhận dưới ảnh gốc
        await channel.send(
            f"✅ {core_disp} **{core_name}** — Đã cộng **{core_value:,} silver** vào bank của {author.mention}\n"
            f"_Ghi nhận bởi {reactor.mention}_",
            reference=message
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        core_ch_id = self.config.get("core_channel_id")
        bank_ch_id = self.config.get("bank_channel_id")
        emoji_map = self.config.get("emoji_map", {})

        if not core_ch_id:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        channel = guild.get_channel(payload.channel_id) or guild.get_thread(payload.channel_id)
        if not channel:
            try:
                channel = await guild.fetch_channel(payload.channel_id)
            except Exception as e:
                print(f"[Error] {e}")
                return
            
        is_core = str(payload.channel_id) == core_ch_id
        if not is_core and hasattr(channel, "parent_id"):
            is_core = str(channel.parent_id) == core_ch_id
            
        if not is_core:
            return

        emoji_key = get_reaction_key(payload.emoji)
        if emoji_key not in emoji_map:
            return

        credit_key = f"{payload.message_id}:{emoji_key}"
        
        entry = None
        try:
            res, err = execute(lambda c: c.table("core_credited").select("*").eq("message_id", credit_key))
            if err:
                print(f"Lỗi kiểm tra core_credited khi remove: {err}")
                return
            if not res or not res.data:
                return # Chưa từng cộng
            entry = res.data[0]
        except Exception as e:
            print(f"Lỗi kiểm tra core_credited khi remove: {e}")
            return

        # Chỉ hoàn lại nếu chính Officer đó gỡ react
        if str(payload.user_id) != entry["user_id"]:
            return

        # Xóa record
        try:
            _, err = execute(lambda c: c.table("core_credited").delete().eq("message_id", credit_key))
            if err:
                print(f"Lỗi xóa core_credited: {err}")
        except Exception as e:
            print(f"Lỗi xóa core_credited: {e}")
            pass

        core_info = emoji_map[emoji_key]
        core_value = core_info["value"]
        core_name = core_info["name"]
        core_disp = core_info.get("display", emoji_key)
        
        # Tìm lại author
        member_id = None
        try:
            message = await channel.fetch_message(payload.message_id)
            author = message.author
            if author.id == self.bot.user.id and "Ảnh tách ra từ <@" in message.content:
                match = re.search(r"Ảnh tách ra từ <@!?(\d+)>", message.content)
                if match:
                    member_id = int(match.group(1))
            else:
                member_id = author.id
        except Exception as e:
            print(f"[Error] fetch message on revert: {e}")
            return
            
        if not member_id:
            return
            
        member = guild.get_member(member_id)
        member_mention = member.mention if member else f"<@{member_id}>"
        reactor = guild.get_member(payload.user_id)
        reactor_mention = reactor.mention if reactor else f"<@{payload.user_id}>"

        token = self.config.get("unbelievaboat_token")
        if token:
            api_url = f"https://unbelievaboat.com/api/v1/guilds/{payload.guild_id}/users/{member_id}"
            headers = {"Authorization": token}
            payload_data = {"bank": -core_value, "reason": f"CoreBank Revert: {core_name}"}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.patch(api_url, headers=headers, json=payload_data):
                        pass
            except Exception as e:
                print(f"[Error] revert API: {e}")
                pass

        if channel:
            try:
                await channel.send(
                    f"↩️ **Hoàn tác** {core_disp} {core_name} — Đã trừ lại **{core_value:,} silver** của {member_mention}\n"
                    f"_Gỡ bởi {reactor_mention}_",
                    reference=message
                )
            except Exception as e:
                print(f"[Error] {e}")
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreBankCog(bot))

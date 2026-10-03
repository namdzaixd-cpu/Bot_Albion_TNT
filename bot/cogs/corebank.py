import re
import aiohttp

import discord
from discord import app_commands
from discord.ext import commands

from core.permissions import is_officer
from core.config_store import get_config_async, invalidate
from core.db import DBError, async_execute
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

def _response_data(response):
    return getattr(response, "data", None) if response is not None else None


def _rpc_json(response):
    data = _response_data(response)
    if isinstance(data, list):
        return data[0] if data else None
    return data

class CoreBankCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = self._default_config()
        self.config_loaded = False

    @staticmethod
    def _default_config():
        return {
            "guild_id": str(GUILD_ID),
            "core_channel_id": "",
            "bank_channel_id": "",
            "unbelievaboat_token": "",
            "emoji_map": {},
            "auto_react": True,
        }

    async def cog_load(self):
        try:
            await self._reload_config()
        except DBError as error:
            print(f"❌ [Core-Bank] Không tải được cấu hình; chưa kích hoạt xử lý Core: {error}")

    async def _reload_config(self):
        guild_id = str(GUILD_ID)
        invalidate("corebank_config", guild_id)
        data = await get_config_async(
            "corebank_config",
            guild_id=guild_id,
            default=None,
        )
        if data is None:
            data = await self._call_rpc(
                "dashboard_get_corebank_config",
                {"p_guild_id": guild_id},
            )
            invalidate("corebank_config", guild_id)
        self.config = {**self._default_config(), **(data or {})}
        self.config_loaded = True

    async def _run_config_rpc(self, name: str, params: dict, *, refresh: bool = True) -> bool:
        _, error = await async_execute(
            lambda client: client.rpc(name, params),
            retries=1,
        )
        if error:
            raise DBError(error)

        if not refresh:
            invalidate("corebank_config", str(GUILD_ID))
            return True
        try:
            await self._reload_config()
        except Exception as exc:
            print(f"⚠️ [Core-Bank] Cấu hình đã lưu nhưng bot chưa tải lại được: {exc}")
            return False
        return True

    async def _patch_config(self, patch: dict) -> bool:
        return await self._run_config_rpc(
            "dashboard_patch_corebank_config",
            {"p_guild_id": str(GUILD_ID), "p_patch": patch},
        )

    async def _mutate_emoji(
        self, key: str, value: dict | None, remove: bool, *, refresh: bool = True
    ) -> bool:
        return await self._run_config_rpc(
            "dashboard_mutate_corebank_emoji",
            {
                "p_guild_id": str(GUILD_ID),
                "p_key": key,
                "p_value": value,
                "p_remove": remove,
            },
            refresh=refresh,
        )

    async def _call_rpc(self, name: str, params: dict):
        response, error = await async_execute(
            lambda client: client.rpc(name, params),
            retries=1,
        )
        if error:
            raise DBError(error)
        return _rpc_json(response)

    async def _transition(self, message_id: str, expected: str, next_status: str) -> bool:
        changed = await self._call_rpc(
            "transition_core_credit",
            {
                "p_message_id": message_id,
                "p_expected_status": expected,
                "p_next_status": next_status,
            },
        )
        return changed is True

    @commands.Cog.listener()
    async def on_config_reload(self):
        try:
            await self._reload_config()
        except Exception as exc:
            print(f"⚠️ [Core-Bank] Không thể tải cấu hình mới: {exc}")
            return
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
                    emoji_map = core_config.get("emoji_map", {}) if message.attachments else {}

                    # Xử lý tách ảnh nếu có nhiều hơn 1 ảnh
                    if len(message.attachments) > 1:
                        await message.reply("🔄 Phát hiện nhiều ảnh, bot đang tách ra thành từng tin nhắn để dễ chấm điểm...")
                        all_reposted = True
                        for i, att in enumerate(message.attachments):
                            try:
                                file = await att.to_file()
                                text = f"📸 Ảnh tách ra từ {message.author.mention} (Ảnh {i+1}/{len(message.attachments)})"
                                if i == 0 and message.content:
                                    text += f"\n📝 Lời nhắn gốc: {message.content}"
                                split_msg = await message.channel.send(content=text, file=file)

                                if emoji_map:
                                    for key in _sorted_emoji_keys(emoji_map):
                                        try:
                                            emoji_str = emoji_map[key]["display"]
                                            reaction = discord.PartialEmoji.from_str(emoji_str) if ":" in emoji_str else emoji_str
                                            await split_msg.add_reaction(reaction)
                                        except Exception as e:
                                            print(f"[Error] {e}")
                            except Exception as e:
                                all_reposted = False
                                print(f"⚠️ [Core-Bank] Lỗi khi tách ảnh: {e}")

                        if all_reposted:
                            try:
                                await message.delete()
                            except Exception as e:
                                print(f"[Error] {e}")
                        return

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
        await interaction.response.defer(ephemeral=True)
        try:
            applied = await self._patch_config({
                "core_channel_id": str(core_channel.id),
                "bank_channel_id": str(bank_channel.id),
                "unbelievaboat_token": token,
            })
        except Exception:
            return await interaction.followup.send("❌ Không thể lưu cấu hình CoreBank.", ephemeral=True)
        note = "" if applied else "\n⚠️ Đã lưu nhưng bot chưa áp dụng được cấu hình mới; hãy reload lại bot."
        await interaction.followup.send(
            f"✅ Đã cài đặt Core-Bank:\n"
            f"📸 Core channel: {core_channel.mention}\n"
            f"💰 Bank channel: {bank_channel.mention}\n"
            f"🔑 UnbelievaBoat Token: **Đã cài ✅**{note}",
            ephemeral=True,
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
        names = [n.strip() for n in name.split(",")]
        values = [v.strip() for v in value.split(",")]
        orders = [o.strip() for o in order.split(",")] if order.strip() else []
        count = len(emojis)
        if len(names) != count or len(values) != count:
            return await interaction.response.send_message(
                "⚠️ Số lượng emoji, tên và giá trị phải bằng nhau!\n"
                "Ví dụ: `/coreadd 🟢,🔵 Green Core,Blue Core 100000,200000`",
                ephemeral=True,
            )

        operations, errors = [], []
        for i in range(count):
            try:
                amount = int(values[i].replace(".", "").replace(",", ""))
                if amount <= 0:
                    errors.append(f"❌ `{names[i]}`: giá trị phải > 0")
                    continue
                display_order = int(orders[i]) if i < len(orders) and orders[i] else 0
                key, display = parse_emoji_input(emojis[i])
                item = {"name": names[i], "value": amount, "display": display, "order": display_order}
                operations.append((
                    key,
                    item,
                    f"{display} **{names[i]}** — {amount:,} silver (STT: {display_order})",
                ))
            except ValueError:
                errors.append(f"❌ `{values[i]}`: giá trị không hợp lệ")

        if not operations:
            msg = "\n".join(errors) if errors else "⚠️ Không có gì được thêm."
            return await interaction.response.send_message(
                f"📋 Kết quả thêm Core (0/{count} thành công):\n{msg}",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        results, saved = [], 0
        for key, item, description in operations:
            try:
                await self._mutate_emoji(key, item, False, refresh=False)
                saved += 1
                results.append(f"✅ {description}")
            except Exception:
                errors.append(f"❌ `{item['name']}`: không thể lưu cấu hình")

        apply_failed = False
        try:
            await self._reload_config()
        except Exception:
            apply_failed = True
        lines = results + errors
        if apply_failed and saved:
            lines.append("⚠️ Đã lưu nhưng bot chưa tải lại được cấu hình.")
        await interaction.followup.send(
            f"📋 Kết quả thêm Core ({saved}/{count} thành công):\n" + "\n".join(lines),
            ephemeral=True,
        )

    @app_commands.command(name="coreremove", description="Xóa emoji Core khỏi danh sách (Officer only)")
    @app_commands.describe(emoji="Emoji muốn xóa")
    async def coreremove_cmd(self, interaction: discord.Interaction, emoji: str):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)
        key, display = parse_emoji_input(emoji)
        await interaction.response.defer(ephemeral=True)
        try:
            await self._reload_config()
        except Exception:
            return await interaction.followup.send("❌ Không thể đọc cấu hình CoreBank.", ephemeral=True)
        removed = self.config.get("emoji_map", {}).get(key)
        if not removed:
            return await interaction.followup.send(
                f"❓ Không tìm thấy emoji `{display}` trong danh sách.",
                ephemeral=True,
            )
        try:
            applied = await self._mutate_emoji(key, None, True)
        except Exception:
            return await interaction.followup.send("❌ Không thể lưu cấu hình CoreBank.", ephemeral=True)
        note = "" if applied else "\n⚠️ Đã lưu nhưng bot chưa áp dụng được cấu hình mới; hãy reload lại bot."
        await interaction.followup.send(
            f"🗑️ Đã xóa: {display} = **{removed['name']}** ({removed['value']:,} silver){note}",
            ephemeral=True,
        )

    @app_commands.command(name="coreautoreact", description="Bật/tắt tự động thả emoji vào ảnh trong kênh Core (Officer only)")
    @app_commands.describe(enable="Bật (True) hoặc Tắt (False)")
    async def coreautoreact_cmd(self, interaction: discord.Interaction, enable: bool):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Chỉ Officer mới dùng được!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            applied = await self._patch_config({"auto_react": enable})
        except Exception:
            return await interaction.followup.send("❌ Không thể lưu cấu hình CoreBank.", ephemeral=True)
        state = "BẬT ✅" if enable else "TẮT ❌"
        note = "" if applied else "\n⚠️ Đã lưu nhưng bot chưa áp dụng được cấu hình mới; hãy reload lại bot."
        await interaction.followup.send(
            f"⚙️ Tự động thả emoji vào ảnh trong kênh Core: **{state}**{note}",
            ephemeral=True,
        )
    @app_commands.command(name="corelist", description="Xem danh sách emoji Core và cấu hình hiện tại")
    async def corelist_cmd(self, interaction: discord.Interaction):
        if not self.config_loaded:
            return await interaction.response.send_message(
                "❌ Không thể đọc cấu hình CoreBank. Vui lòng thử lại sau.", ephemeral=True
            )
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

    async def _reaction_context(self, payload):
        if payload.user_id == self.bot.user.id:
            return None
        core_channel_id = self.config.get("core_channel_id")
        if not core_channel_id:
            return None
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return None
        channel = guild.get_channel(payload.channel_id) or guild.get_thread(payload.channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(payload.channel_id)
            except Exception:
                return None
        if str(payload.channel_id) != core_channel_id and str(getattr(channel, "parent_id", "")) != core_channel_id:
            return None
        reactor = guild.get_member(payload.user_id)
        if reactor is None or not is_officer(reactor):
            return None
        return guild, channel, reactor

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        context = await self._reaction_context(payload)
        if context is None:
            return
        guild, channel, reactor = context
        emoji_key = get_reaction_key(payload.emoji)
        core_info = self.config.get("emoji_map", {}).get(emoji_key)
        if not core_info:
            return
        token = self.config.get("unbelievaboat_token")
        bank_channel_id = self.config.get("bank_channel_id")
        try:
            bank_channel = guild.get_channel(int(bank_channel_id)) if bank_channel_id else None
        except (TypeError, ValueError):
            bank_channel = None
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return
        author = message.author
        if author.id == self.bot.user.id and "Ảnh tách ra từ <@" in message.content:
            match = re.search(r"Ảnh tách ra từ <@!?(\d+)>", message.content)
            member = guild.get_member(int(match.group(1))) if match else None
            if member is None:
                return
            author = member
        if author.bot:
            return
        if not token:
            await channel.send(
                "⚠️ Chưa cài UnbelievaBoat API Token! Hãy dùng `/coresetup`.",
                reference=message,
            )
            return
        if bank_channel is None:
            await channel.send(
                "⚠️ Chưa cài bank channel! Dùng `/coresetup` trước.",
                reference=message,
            )
            return

        amount = core_info.get("value")
        if not isinstance(amount, int) or amount <= 0:
            return
        credit_key = f"{payload.message_id}:{emoji_key}"
        snapshot = {
            "p_message_id": credit_key,
            "p_guild_id": str(payload.guild_id),
            "p_officer_id": str(reactor.id),
            "p_recipient_id": str(author.id),
            "p_amount": amount,
            "p_emoji_key": emoji_key,
            "p_core_name": str(core_info["name"]),
            "p_core_display": str(core_info.get("display", emoji_key)),
        }
        try:
            claim = await self._call_rpc("claim_core_credit", snapshot)
        except Exception as exc:
            print(f"Lỗi claim core_credited: {exc}")
            return
        if not isinstance(claim, dict) or not claim.get("claimed"):
            return
        entry = claim.get("entry")
        if not isinstance(entry, dict):
            return
        amount = entry.get("amount")
        recipient_id = entry.get("recipient_id")
        guild_id = entry.get("guild_id")
        core_name = entry.get("core_name")
        core_display = entry.get("core_display")
        if (
            not isinstance(amount, int)
            or amount <= 0
            or not recipient_id
            or not guild_id
            or not core_name
            or not core_display
        ):
            return
        api_url = f"https://unbelievaboat.com/api/v1/guilds/{guild_id}/users/{recipient_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    api_url,
                    headers={"Authorization": token},
                    json={"bank": amount, "reason": f"CoreBank: {core_name}"},
                ) as response:
                    if response.status not in (200, 204):
                        await self._transition(credit_key, "pending", "unknown")
                        await channel.send(
                            f"⚠️ UnbelievaBoat trả HTTP {response.status}; khoản Core đang chờ đối soát, không tự gửi lại.",
                            reference=message,
                        )
                        return
        except Exception as exc:
            try:
                await self._transition(credit_key, "pending", "unknown")
            except Exception as transition_error:
                print(f"Lỗi đánh dấu Core chưa rõ kết quả: {transition_error}")
            print(f"Lỗi kết nối API UnbelievaBoat; giữ claim để đối soát: {exc}")
            return

        try:
            credited = await self._transition(credit_key, "pending", "credited")
        except Exception as exc:
            print(f"UnbelievaBoat đã trả thành công nhưng không lưu được trạng thái Core; cần đối soát: {exc}")
            return
        if not credited:
            print(f"UnbelievaBoat đã trả thành công nhưng claim {credit_key} không còn pending; cần đối soát.")
            return
        await channel.send(
            f"✅ {core_display} **{core_name}** — "
            f"Đã cộng **{amount:,} silver** vào bank của <@{recipient_id}>\n"
            f"_Ghi nhận bởi {reactor.mention}_",
            reference=message,
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        context = await self._reaction_context(payload)
        if context is None:
            return
        guild, channel, reactor = context
        credit_key = f"{payload.message_id}:{get_reaction_key(payload.emoji)}"
        response, error = await async_execute(
            lambda client: client.table("core_credited")
            .select("*")
            .eq("message_id", credit_key),
            retries=1,
        )
        if error:
            print(f"Lỗi truy vấn core_credited khi remove: {error}")
            return
        rows = response.data if response is not None else []
        if not rows:
            return
        entry = rows[0]
        amount = entry.get("amount")
        if (
            entry.get("status") != "credited"
            or not entry.get("recipient_id")
            or not entry.get("guild_id")
            or not entry.get("emoji_key")
            or not entry.get("core_name")
            or not entry.get("core_display")
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount <= 0
        ):
            return
        if entry.get("user_id") != str(payload.user_id) or entry["guild_id"] != str(payload.guild_id):
            return
        token = self.config.get("unbelievaboat_token")
        if not token:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            message = None

        try:
            started = await self._transition(credit_key, "credited", "reverting")
        except Exception as exc:
            print(f"Lỗi chuyển Core sang reverting: {exc}")
            return
        if not started:
            return

        recipient_id = entry["recipient_id"]
        api_url = f"https://unbelievaboat.com/api/v1/guilds/{entry['guild_id']}/users/{recipient_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    api_url,
                    headers={"Authorization": token},
                    json={"bank": -amount, "reason": f"CoreBank Revert: {entry['core_name']}"},
                ) as response:
                    if response.status not in (200, 204):
                        await self._transition(credit_key, "reverting", "refund_unknown")
                        if message:
                            await channel.send(
                                f"⚠️ UnbelievaBoat trả HTTP {response.status}; hoàn Core chờ đối soát, không tự gửi lại.",
                                reference=message,
                            )
                        return
        except Exception as exc:
            try:
                await self._transition(credit_key, "reverting", "refund_unknown")
            except Exception as transition_error:
                print(f"Lỗi đánh dấu hoàn Core chưa rõ kết quả: {transition_error}")
            print(f"Lỗi kết nối API khi hoàn Core; giữ ledger để đối soát: {exc}")
            return

        try:
            reverted = await self._transition(credit_key, "reverting", "reverted")
        except Exception as exc:
            print(f"UnbelievaBoat đã trừ tiền nhưng không lưu được trạng thái hoàn Core: {exc}")
            return
        if not reverted:
            print(f"UnbelievaBoat đã trừ tiền nhưng ledger {credit_key} không còn reverting; cần đối soát.")
            return
        member = guild.get_member(int(recipient_id))
        member_mention = member.mention if member else f"<@{recipient_id}>"
        if message:
            await channel.send(
                f"↩️ **Hoàn tác** {entry['core_display']} {entry['core_name']} — "
                f"Đã trừ lại **{amount:,} silver** của {member_mention}\n"
                f"_Gỡ bởi {reactor.mention}_",
                reference=message,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreBankCog(bot))

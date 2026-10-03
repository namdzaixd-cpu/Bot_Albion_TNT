import os
import asyncio
import weakref

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from core.config import STORAGE_DIR, GEMINI_API_KEY
from core.permissions import is_officer
from core.storage import load_json_async, save_json_async

# ==============================================================================
# HỆ THỐNG: TỰ ĐỘNG TẠO THREAD + DỊCH KÊNH #UPDATE (Gemini)
#
# - Tự động tạo 1 thread gắn vào mỗi message cập nhật trong kênh #update.
# - Gọi Gemini đặt tiêu đề thread (AI tự viết theo nội dung) + dịch sang tiếng Việt,
#   post bản dịch vào thread.
# - Cho phép user react 🇻🇳 hoặc tag bot để yêu cầu dịch lại tin.
# ==============================================================================

CONFIG_FILE = os.path.join(STORAGE_DIR, "tnc_updatetranslator_v1.json")
CONFIG_DEFAULT = lambda: {"enabled": True, "channel_ids": []}


async def load_config():
    return await load_json_async(CONFIG_FILE, CONFIG_DEFAULT)


async def save_config(data):
    return await save_json_async(data, CONFIG_FILE)


GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
FLAG_EMOJI = "🇻🇳"
MAX_MSG_LEN = 2000


async def gemini_request(prompt: str) -> str | None:
    """Gọi Gemini REST, trả text đầu ra. Trả None nếu thiếu key / lỗi (CI-safe)."""
    if not GEMINI_API_KEY:
        print("[UpdateTranslator] Thiếu GEMINI_API_KEY — bỏ qua nhờ Gemini")
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000},
    }
    headers = {"Content-Type": "application/json"}
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    print(f"[UpdateTranslator] Gemini HTTP {resp.status}")
                    return None
                data = await resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        text = candidates[0]["content"]["parts"][0].get("text", "").strip()
        return text or None
    except Exception as e:  # noqa: BLE001 — an toàn tuyệt đối, không crash bot
        print(f"[UpdateTranslator] Gemini lỗi: {e}")
        return None


def get_channel_text(message: discord.Message) -> str:
    """Rút nội dung text của message bài chính (loại mention hình thức)."""
    text = (message.content or "").strip()
    if not text:
        return ""
    # Bỏ phần mention bot ở đầu nếu người dùng tag bot để yêu cầu dịch
    text = discord.utils.remove_markdown(text).strip()
    return text


def split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Cắt text dài thành nhiều chunk <= limit ký tự (cắt theo dòng nếu có)."""
    if len(text) <= limit:
        return [text]
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


class UpdateTranslatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.in_progress = set()
        self._thread_locks = weakref.WeakValueDictionary()
        self._config_lock = asyncio.Lock()

    def _thread_lock(self, message_id):
        return self._thread_locks.setdefault(message_id, asyncio.Lock())

    async def target_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        cfg = await load_config()
        if not cfg.get("enabled"):
            return []
        channels = []
        for channel_id in cfg.get("channel_ids") or []:
            channel = guild.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                channels.append(channel)
        return channels

    def lookup_channel(self, guild: discord.Guild, name: str) -> discord.TextChannel | None:
        target = name.strip()
        # Nếu user dán ID channel hoặc link Discord hoặc mention <#ID>
        import re
        m = re.search(r"\d{15,20}", target)
        if m:
            ch = guild.get_channel(int(m.group(0)))
            if isinstance(ch, discord.TextChannel):
                return ch
        target = target.lower().lstrip("#")
        for ch in guild.text_channels:
            if ch.name.lower() == target:
                return ch
        for ch in guild.text_channels:
            if target in ch.name.lower():
                return ch
        return None

    # ============================================================
    # Listeners
    # ============================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return  # bỏ qua message trong thread / forum / DM
        # bỏ qua lệnh prefix
        if message.content.startswith(("!", ".")):
            return

        try:
            channels = await self.target_channels(message.guild)
        except Exception as error:
            print(f"[UpdateTranslator] không đọc được cấu hình: {error}")
            return
        if message.channel not in channels:
            return

        # Yêu cầu dịch: user reply 1 tin vào #update đã cấu hình + tag @Bot
        # => bot tạo thread dính vào tin reply + dịch sang tiếng Việt.
        if self.bot.user in message.mentions and message.reference:
            await self._handle_translate_request(message)
            return
        try:
            await self._auto_process(message)
        except Exception as error:
            print(f"[UpdateTranslator] không xử lý được message {message.id}: {error}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.emoji.name != FLAG_EMOJI:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        guild = channel.guild
        try:
            channels = await self.target_channels(guild)
        except Exception as error:
            print(f"[UpdateTranslator] không đọc được cấu hình: {error}")
            return
        if channel not in channels:
            return
        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if msg.author.bot:
            return  # không đặt bản dịch lên chính bản dịch của bot
        try:
            await self._ensure_translation(msg)
        except Exception as error:
            print(f"[UpdateTranslator] không xử lý được reaction {msg.id}: {error}")

    # ============================================================
    # Xử lý chính
    # ============================================================
    async def _auto_process(self, message: discord.Message):
        """Message mới trong #update → tạo thread + đặt title + dịch."""
        # bỏ qua nếu message đã xử lý rồi (có thread/bản dịch lưu trong memory map)
        if await self._already_done(message):
            return
        await self._ensure_translation(message)

    async def _handle_translate_request(self, message: discord.Message):
        """Reply + tag @Bot trong kênh #update đã cấu hình:
        tạo thread dính vào tin được reply + dịch nội dung sang tiếng Việt."""
        target = message.reference.resolved if message.reference else None
        if target is None:
            # reference không resolve được (đôi khi gateway trả None) → nhờ tin phía trên
            try:
                async for m in message.channel.history(limit=20, before=message):
                    if not m.author.bot and m.content.strip():
                        target = m
                        break
            except discord.Forbidden:
                target = None
        if target is None:
            await message.reply("🤔 Tôi không tìm thấy tin cập nhật nào để dịch.")
            return

        # Nếu reference chỉ còn DeletedReferencedMessage (tin đã bị xóa) → không có content
        if not getattr(target, "content", ""):
            await message.reply("❌ Tin được reply không tồn tại hoặc không có nội dung text để dịch.")
            return

        text = get_channel_text(target)
        if not text:
            await message.reply("❌ Tin này không có nội dung text để dịch.")
            return

        # tạo thread dính vào tin reply (nếu chưa có) + dịch
        try:
            thread = await self._get_or_create_thread(target, text)
            translated = await self._translate(text)
            if translated:
                await self._post_to_thread(thread, translated)
            guild_id = message.guild.id if message.guild else 0
            link = f"https://discord.com/channels/{guild_id}/{thread.id}"
            await message.reply(f"✅ Đã tạo thread **#{thread.name}** + bản dịch: {link}")
        except Exception as e:  # noqa: BLE001
            print(f"[UpdateTranslator] lỗi tạo thread khi tag bot: {e}")
            await message.reply(f"❌ Lỗi khi tạo thread: `{e}`")

    async def _ensure_translation(self, message: discord.Message):
        """Đảm bảo message có 1 thread + bản dịch tiếng Việt. Idempotent."""
        if message.id in self.in_progress:
            return
        self.in_progress.add(message.id)
        try:
            text = get_channel_text(message)
            if not text:
                # tin chỉ có media/embed — vẫn tạo thread ghi chú
                text = "[Không có nội dung text — tin này là hình ảnh/link]"
                translated = None
            else:
                translated = await self._translate(text)

            thread = await self._get_or_create_thread(message, text)
            if translated:
                await self._post_to_thread(thread, translated)
        except Exception as error:
            print(f"[UpdateTranslator] lỗi xử lý {message.id}: {error}")
            raise

    async def _translate(self, text: str) -> str | None:
        prompt = (
            "Bạn là biên dịch viên game. Dịch đoạn cập nhật sau sang tiếng Việt tự nhiên, "
            "giữ nguyên tên riêng, số liệu, tên vật phẩm/kỹ năng, định dạng bullet/list.\n\n"
            f"{text}"
        )
        return await gemini_request(prompt)

    async def _get_or_create_thread(self, message: discord.Message, text: str) -> discord.Thread:
        """Fetch the mapped thread (unarchiving if needed), creating only when missing."""
        async with self._thread_lock(message.id):
            config = await load_config()
            thread_id = (config.get("threads") or {}).get(str(message.id))
            thread = None
            if thread_id:
                thread = self.bot.get_channel(int(thread_id))
                if not isinstance(thread, discord.Thread):
                    try:
                        thread = await self.bot.fetch_channel(int(thread_id))
                    except discord.NotFound:
                        thread = None
                if thread is not None and not isinstance(thread, discord.Thread):
                    raise TypeError(f"Stored channel {thread_id} is not a thread.")
            if thread is None:
                thread = getattr(message, "thread", None)
            if isinstance(thread, discord.Thread):
                if thread.archived:
                    await thread.edit(archived=False)
                if not thread_id:
                    async with self._config_lock:
                        config = await load_config()
                        config.setdefault("threads", {})[str(message.id)] = thread.id
                        await save_config(config)
                return thread

            title = await self._make_title(text)
            thread = await message.create_thread(
                name=title, auto_archive_duration=1440
            )
            async with self._config_lock:
                config = await load_config()
                config.setdefault("threads", {})[str(message.id)] = thread.id
                await save_config(config)
            return thread

    async def _make_title(self, text: str) -> str:
        """AI đặt tiêu đề thread ngắn theo nội dung. Fallback dòng đầu."""
        if not text:
            return "📢 Cập nhật mới"
        prompt = (
            "Đặt 1 tiêu đề ngắn gọn (tối đa 90 ký tự, tiếng Việt, không thêm emoji đầu) "
            "cho bản cập nhật sau, chỉ trả về tiêu đề:\n\n"
            f"{text[:2000]}"
        )
        title = await gemini_request(prompt)
        if title:
            title = title.split("\n")[0].strip()
            if title:
                return title[:100]
        # fallback: dòng đầu của nội dung
        first = text.split("\n")[0].strip()
        return first[:100] if first else "📢 Cập nhật mới"

    async def _post_to_thread(self, thread: discord.Thread, translated: str):
        await thread.send("🇻🇳 **Bản dịch tiếng Việt:**")
        for part in split_message(translated):
            await thread.send(part)

    async def _translate_and_post(self, message: discord.Message) -> str:
        """Dịch message và post vào thread, trả chuỗi xác nhận gửi cho user."""
        text = get_channel_text(message)
        if not text:
            return "❌ Tin này không có nội dung text để dịch."
        translated = await self._translate(text)
        if not translated:
            return "⚠️ Không dịch được (lỗi Gemini hoặc thiếu key)."
        thread = await self._get_or_create_thread(message, text)
        await self._post_to_thread(thread, translated)
        return f"✅ Đã dịch vào thread **{thread.name}** 🇻🇳"

    async def _already_done(self, message: discord.Message) -> bool:
        """True nếu message đã có thread trong mapping (đã xử lý trước đó)."""
        config = await load_config()
        return str(message.id) in (config.get("threads") or {})

    # ============================================================
    # Slash commands
    # ============================================================
    @app_commands.command(name="utconfig", description="Cấu hình kênh #update tự dịch (Officer)")
    @app_commands.describe(channel="Tên kênh #update (vd: update)", enable="Bật/tắt tính năng")
    @app_commands.choices(enable=[
        app_commands.Choice(name="Bật", value="on"),
        app_commands.Choice(name="Tắt", value="off"),
    ])
    async def utconfig_cmd(
        self,
        interaction: discord.Interaction,
        channel: str = None,
        enable: app_commands.Choice[str] = None,
    ):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
        guild = interaction.guild
        selected_channel = self.lookup_channel(guild, channel) if channel and guild else None
        if channel and not selected_channel:
            return await interaction.response.send_message(
                f"❌ Không tìm thấy kênh tên chứa `{channel}` trong server.", ephemeral=True
            )
        if not channel and not enable:
            return await interaction.response.send_message(
                "Dùng `/utconfig channel:<tên>` để thêm kênh, `/utconfig enable:on|off` để bật/tắt.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        try:
            async with self._config_lock:
                config = await load_config()
                if selected_channel:
                    channel_ids = config.setdefault("channel_ids", [])
                    if selected_channel.id not in channel_ids:
                        channel_ids.append(selected_channel.id)
                    success = f"✅ Đã thêm kênh **#{selected_channel.name}** vào danh sách tự dịch."
                else:
                    config["enabled"] = enable.value == "on"
                    state = "BẬT ✅" if config["enabled"] else "TẮT ❌"
                    success = f"⚙️ Tính năng tự dịch #update: **{state}**"
                await save_config(config)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể lưu cấu hình: `{error}`", ephemeral=True)
        await interaction.edit_original_response(content=success)

    @app_commands.command(name="utstatus", description="Xem cấu hình kênh #update + trạng thái dịch")
    async def utstatus_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            config = await load_config()
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể đọc cấu hình: `{error}`", ephemeral=True)
        guild = interaction.guild
        lines = [f"🔛 Trạng thái: **{'BẬT' if config.get('enabled') else 'TẮT'}**"]
        if config.get("channel_ids"):
            names = []
            for channel_id in config["channel_ids"]:
                channel = guild.get_channel(int(channel_id)) if guild else None
                names.append(f"#{channel.name}" if channel else f"`{channel_id}` (không tìm thấy)")
            lines.append(f"📌 Kênh: {', '.join(names)}")
        else:
            lines.append("📌 Kênh: chưa cấu hình (dùng `/utconfig channel:<tên>`)")
        lines.append(f"🤖 Gemini API key: {'✅ Có' if GEMINI_API_KEY else '❌ Thiếu'}")
        lines.append(f"🧵 Số thread đã tạo: {len(config.get('threads') or {})}")
        await interaction.edit_original_response(content="\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(UpdateTranslatorCog(bot))

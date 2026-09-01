import os

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from core.config import STORAGE_DIR, GEMINI_API_KEY
from core.permissions import is_officer
from core.storage import load_json, save_json

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


def load_config():
    return load_json(CONFIG_FILE, CONFIG_DEFAULT)


def save_config(data):
    save_json(data, CONFIG_FILE)


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
        # in_progress[message_id] = True — chống chạy trùng (gateway có thể gửi lặp)
        self.in_progress = set()

    # ============================================================
    # Utils
    # ============================================================
    def target_channels(self, guild: discord.Guild) -> list[discord.TextChannel]:
        """Trả danh sách TextChannel trong guild mà tính năng đang bật."""
        cfg = load_config()
        if not cfg.get("enabled"):
            return []
        ids = cfg.get("channel_ids") or []
        channels = []
        for cid in ids:
            ch = guild.get_channel(cid)
            if isinstance(ch, discord.TextChannel):
                channels.append(ch)
        return channels

    def lookup_channel(self, guild: discord.Guild, name: str) -> discord.TextChannel | None:
        target = name.lower().lstrip("#")
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

        channels = self.target_channels(message.guild)
        if message.channel not in channels:
            return

        # Nếu là yêu cầu dịch (tag bot/user) thì xử lý riêng
        if self.bot.user in message.mentions:
            await self._handle_translate_request(message)
            return

        await self._auto_process(message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.emoji.name != FLAG_EMOJI:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        guild = channel.guild
        if channel not in self.target_channels(guild):
            return
        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if msg.author.bot:
            return  # không đặt bản dịch lên chính bản dịch của bot
        await self._ensure_translation(msg)

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
        """Tag bot trong #update: tìm message được reply (hoặc tin trên) và dịch."""
        target = message.reference.resolved if message.reference else None
        if target is None:
            # tìm message phía trên không phải bot, trong kênh
            try:
                async for m in message.channel.history(limit=20, before=message):
                    if not m.author.bot and m.content.strip():
                        target = m
                        break
            except discord.Forbidden:
                target = None
        if target is None:
            await message.channel.send("🤔 Tôi không tìm thấy tin cập nhật nào để dịch ở phía trên.")
            return
        if message.channel not in self.target_channels(message.guild):
            return
        # phản hồi tại chỗ tin nhắn tag (không tạo thread riêng)
        await message.reply(await self._translate_and_post(target))

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
        except Exception as e:  # noqa: BLE001
            print(f"[UpdateTranslator] lỗi xử lý {message.id}: {e}")
        finally:
            self.in_progress.discard(message.id)

    async def _translate(self, text: str) -> str | None:
        prompt = (
            "Bạn là biên dịch viên game. Dịch đoạn cập nhật sau sang tiếng Việt tự nhiên, "
            "giữ nguyên tên riêng, số liệu, tên vật phẩm/kỹ năng, định dạng bullet/list.\n\n"
            f"{text}"
        )
        return await gemini_request(prompt)

    async def _get_or_create_thread(self, message: discord.Message, text: str) -> discord.Thread:
        """Tìm thread đã tồn tại cho message, nếu chưa có thì tạo mới kèm title AI."""
        mem = load_config().get("threads") or {}
        tid = mem.get(str(message.id))
        if tid:
            thread = self.bot.get_channel(tid)
            if isinstance(thread, discord.Thread):
                return thread

        title = await self._make_title(text)
        thread = await message.create_thread(
            name=title, auto_archive_duration=1440  # archive sau 1 giờ, đủ cho discussion
        )
        # lưu mapping message_id -> thread_id
        cfg = load_config()
        cfg.setdefault("threads", {})[str(message.id)] = thread.id
        save_config(cfg)
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
        mem = load_config().get("threads") or {}
        return str(message.id) in mem

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
        cfg = load_config()
        guild = interaction.guild

        if channel:
            ch = self.lookup_channel(guild, channel)
            if not ch:
                return await interaction.response.send_message(
                    f"❌ Không tìm thấy kênh tên chứa `{channel}` trong server.", ephemeral=True
                )
            ids = cfg.setdefault("channel_ids", [])
            if ch.id not in ids:
                ids.append(ch.id)
            save_config(cfg)
            await interaction.response.send_message(
                f"✅ Đã thêm kênh **#{ch.name}** vào danh sách tự dịch.", ephemeral=True
            )
            return

        if enable:
            cfg["enabled"] = (enable.value == "on")
            save_config(cfg)
            state = "BẬT ✅" if cfg["enabled"] else "TẮT ❌"
            await interaction.response.send_message(f"⚙️ Tính năng tự dịch #update: **{state}**", ephemeral=True)
            return

        await interaction.response.send_message(
            "Dùng `/utconfig channel:<tên>` để thêm kênh, `/utconfig enable:on|off` để bật/tắt.",
            ephemeral=True,
        )

    @app_commands.command(name="utstatus", description="Xem cấu hình kênh #update + trạng thái dịch")
    async def utstatus_cmd(self, interaction: discord.Interaction):
        cfg = load_config()
        guild = interaction.guild
        lines = []
        lines.append(f"🔛 Trạng thái: **{'BẬT' if cfg.get('enabled') else 'TẮT'}**")
        if cfg.get("channel_ids"):
            names = []
            for cid in cfg["channel_ids"]:
                ch = guild.get_channel(cid) if guild else None
                names.append(f"#{ch.name}" if ch else f"`{cid}` (không tìm thấy)")
            lines.append(f"📌 Kênh: {', '.join(names)}")
        else:
            lines.append("📌 Kênh: chưa cấu hình (dùng `/utconfig channel:<tên>`)")
        key_state = "✅ Có" if GEMINI_API_KEY else "❌ Thiếu"
        lines.append(f"🤖 Gemini API key: {key_state}")
        nt = len(cfg.get("threads") or {})
        lines.append(f"🧵 Số thread đã tạo: {nt}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(UpdateTranslatorCog(bot))

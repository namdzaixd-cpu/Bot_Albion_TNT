import asyncio
import os
import re
import tempfile

import discord
from discord import app_commands
from discord.ext import commands
from gtts import gTTS

from core.config import DATA_DIR
from core.permissions import is_officer
from core.db import async_execute

# ==============================================================================
# HỆ THỐNG TTS VOICE "ALO" (Bot join voice, đọc chat bằng giọng Google TTS)
# ==============================================================================

MENTION_RE = re.compile(r"<@!?(\d+)>")
CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
CUSTOM_EMOJI_RE = re.compile(r"<a?:(\w+):\d+>")
URL_RE = re.compile(r"https?://\S+")


async def load_tts_config():
    data = {"read_name": {}, "rejoin": {}}
    response, error = await async_execute(
        lambda client: client.table("alo_tts_config").select("*").eq("id", 1)
    )
    if error:
        raise RuntimeError(f"Error loading alo_tts_config: {error}")
    if response and response.data:
        row = response.data[0]
        data["read_name"] = row.get("read_name", {})
        data["rejoin"] = row.get("rejoin", {})
    return data


async def save_tts_config(data):
    record = {
        "id": 1,
        "read_name": data.get("read_name", {}),
        "rejoin": data.get("rejoin", {}),
    }
    _, error = await async_execute(
        lambda client: client.table("alo_tts_config").upsert(record)
    )
    if error:
        raise RuntimeError(f"Error saving alo_tts_config: {error}")


def clean_text_for_tts(message: discord.Message) -> str:
    """Làm sạch nội dung tin nhắn trước khi đưa qua TTS (mention, link, emoji custom...)."""
    text = message.content or ""
    text = URL_RE.sub("đường link", text)

    def repl_mention(m):
        uid = int(m.group(1))
        member = message.guild.get_member(uid) if message.guild else None
        return member.display_name if member else "ai đó"

    def repl_channel(m):
        ch = message.guild.get_channel(int(m.group(1))) if message.guild else None
        return f"kênh {ch.name}" if ch else "một kênh"

    text = MENTION_RE.sub(repl_mention, text)
    text = CHANNEL_MENTION_RE.sub(repl_channel, text)
    text = CUSTOM_EMOJI_RE.sub(lambda m: m.group(1), text)
    return text.strip()


def generate_tts_file(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".mp3", dir=DATA_DIR)
    os.close(fd)
    tts = gTTS(text=text, lang="vi")
    tts.save(path)
    return path


class AloTtsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._config_lock = asyncio.Lock()
        # voice_sessions[guild_id] = {"channel_id": int, "intentional_leave": bool}
        self.voice_sessions = {}
        # mute_state[guild_id] = True/False (tạm tắt tiếng đọc, bot vẫn ở lại voice)
        self.mute_state = {}
        # tts_queues[guild_id] = asyncio.Queue chứa text cần đọc
        self.tts_queues = {}
        # tts_workers[guild_id] = asyncio.Task đang xử lý queue
        self.tts_workers = {}
        # cờ đánh dấu đã chạy tự động vào lại voice sau khi khởi động (tránh reconnect storm khi gateway resume)
        self._startup_reconnect_done = False

    async def enqueue_tts(
        self, guild: discord.Guild, text: str, author_name: str, source_channel_id: int
    ):
        if not text or not text.strip():
            return
        guild_id = guild.id
        config = await load_tts_config()
        read_name = config.get("read_name", {}).get(str(guild_id), True)
        full_text = f"{author_name} nói: {text}" if read_name else text

        if guild_id not in self.tts_queues:
            self.tts_queues[guild_id] = asyncio.Queue()
        await self.tts_queues[guild_id].put((source_channel_id, full_text))

        if guild_id not in self.tts_workers or self.tts_workers[guild_id].done():
            self.tts_workers[guild_id] = self.bot.loop.create_task(self._tts_worker(guild_id))
    
    async def _tts_worker(self, guild_id):
        queue = self.tts_queues[guild_id]
        while not queue.empty():
            source_channel_id, text = await queue.get()
            if self.mute_state.get(guild_id):
                continue
            session = self.voice_sessions.get(guild_id)
            if not session or source_channel_id != session.get("channel_id"):
                continue
            guild = self.bot.get_guild(guild_id)
            vc = guild.voice_client if guild else None
            if not vc or not vc.is_connected() or vc.channel.id != source_channel_id:
                continue

            try:
                path = await self.bot.loop.run_in_executor(None, generate_tts_file, text)
            except Exception as e:
                print(f"❌ [ALO-TTS] Lỗi tạo audio: {e}")
                continue

            finished = asyncio.Event()

            def after_play(err, path=path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"[Error] {e}")
                    pass
                self.bot.loop.call_soon_threadsafe(finished.set)

            try:
                while vc.is_playing():
                    await asyncio.sleep(0.5)
                current_session = self.voice_sessions.get(guild_id)
                if (
                    self.mute_state.get(guild_id)
                    or not current_session
                    or current_session.get("channel_id") != source_channel_id
                    or not vc.is_connected()
                    or vc.channel.id != source_channel_id
                ):
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass
                    continue
                # Giới hạn tối đa 1 phút/đoạn bằng option ffmpeg "-t 60"
                vc.play(discord.FFmpegPCMAudio(path, options="-t 60"), after=after_play)
                await finished.wait()
            except Exception as error:
                print(f"❌ [ALO-TTS] Lỗi phát audio: {error}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild and isinstance(message.channel, discord.VoiceChannel) and not message.content.startswith(("!", ".")):
            session = self.voice_sessions.get(message.guild.id)
            if session and session.get("channel_id") == message.channel.id:
                text = clean_text_for_tts(message)
                if text:
                    try:
                        await self.enqueue_tts(
                            message.guild, text, message.author.display_name, message.channel.id
                        )
                    except Exception as error:
                        print(f"❌ [ALO-TTS] Không thể đọc cấu hình TTS: {error}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track bot moves and reconnect after unexpected disconnects."""
        if member.id != self.bot.user.id:
            return
        guild = member.guild

        if before.channel is not None and after.channel is not None:
            session = self.voice_sessions.get(guild.id)
            if session and before.channel.id != after.channel.id:
                session["channel_id"] = after.channel.id
                voice_client = guild.voice_client
                if voice_client and voice_client.is_playing():
                    voice_client.stop()
            return

        if before.channel is not None and after.channel is None:
            session = self.voice_sessions.get(guild.id)
            if session and session.get("intentional_leave"):
                self.voice_sessions.pop(guild.id, None)
                self.mute_state.pop(guild.id, None)
                return

            channel_id = before.channel.id
            try:
                config = await load_tts_config()
            except Exception as error:
                print(f"Error loading alo_tts_config for reconnect: {error}")
                return
            if config.get("rejoin", {}).get(str(channel_id)):
                await asyncio.sleep(3)
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.connect()
                        self.voice_sessions[guild.id] = {"channel_id": channel.id, "intentional_leave": False}
                        print(f"🔄 [ALO] Đã tự rejoin lại {channel.name}")
                    except Exception as error:
                        print(f"⚠️ [ALO] Rejoin thất bại: {error}")
                        self.voice_sessions.pop(guild.id, None)
                else:
                    self.voice_sessions.pop(guild.id, None)
            else:
                self.voice_sessions.pop(guild.id, None)
                self.mute_state.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        """Khi bot khởi động (sau mỗi lần Render redeploy / restart), tự động vào
        lại các voice channel đã bật cấu hình rejoin — chống bot bị văng khỏi voice
        mỗi lần push code lên."""
        if self._startup_reconnect_done:
            return
        self._startup_reconnect_done = True
        # Chạy nền, delay để guild/channel cache load xong trước khi connect
        self.bot.loop.create_task(self._restore_voice_on_startup())

    async def _restore_voice_on_startup(self, retries: int = 6, delay: int = 8):
        await asyncio.sleep(delay)  # chờ gateway + cache kênh ổn định
        try:
            config = await load_tts_config()
        except Exception as error:
            print(f"Error loading alo_tts_config for startup reconnect: {error}")
            return
        rejoin_cfg = config.get("rejoin", {})
        for channel_id_str, enabled in rejoin_cfg.items():
            if not enabled:
                continue
            channel_id = int(channel_id_str)
            for attempt in range(1, retries + 1):
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        # channel chưa nằm trong cache, chờ thêm rồi thử lại
                        await asyncio.sleep(3)
                        continue
                    guild = channel.guild
                    vc = guild.voice_client
                    if vc and vc.is_connected():
                        if vc.channel.id != channel.id:
                            await vc.move_to(channel)
                    else:
                        await channel.connect()
                    self.voice_sessions[guild.id] = {"channel_id": channel.id, "intentional_leave": False}
                    self.mute_state[guild.id] = False
                    print(f"🔄 [ALO] Đã tự vào lại voice {channel.name} sau khi khởi động")
                    break
                except Exception as e:
                    print(f"⚠️ [ALO] Startup reconnect thất bại (lần {attempt}/{retries}): {e}")
                    await asyncio.sleep(5)

    @app_commands.command(name="alojoin", description="Bot join (hoặc kéo qua) voice channel bạn đang đứng")
    async def alojoin_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ Bạn phải đang ở trong 1 voice channel!", ephemeral=True)
        channel = interaction.user.voice.channel
        vc = guild.voice_client

        if vc and vc.channel.id == channel.id:
            self.voice_sessions[guild.id] = {"channel_id": channel.id, "intentional_leave": False}
            return await interaction.response.send_message(f"✅ Bot đã ở **{channel.name}** rồi!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        try:
            if vc:
                await vc.move_to(channel)
            else:
                await channel.connect()
            self.voice_sessions[guild.id] = {"channel_id": channel.id, "intentional_leave": False}
            self.mute_state[guild.id] = False
            await interaction.followup.send(f"✅ Bot đã vào **{channel.name}**! Cứ nhắn chat trong voice là bot đọc.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Không thể join voice: {e}", ephemeral=True)

    @app_commands.command(name="aloleave", description="Bot rời voice hiện tại")
    async def aloleave_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        vc = guild.voice_client
        if not vc:
            return await interaction.response.send_message("❌ Bot không ở voice nào cả!", ephemeral=True)

        session = self.voice_sessions.get(guild.id, {})
        session["intentional_leave"] = True
        self.voice_sessions[guild.id] = session

        channel_name = vc.channel.name
        await interaction.response.defer(ephemeral=True)
        try:
            await vc.disconnect()
        except Exception as error:
            session["intentional_leave"] = False
            return await interaction.followup.send(f"❌ Không thể rời voice: {error}", ephemeral=True)
        self.voice_sessions.pop(guild.id, None)
        self.mute_state.pop(guild.id, None)
        await interaction.followup.send(f"👋 Bot đã rời **{channel_name}**.", ephemeral=True)

    @app_commands.command(name="alonametoggle", description="Bật/tắt đọc tên người gửi trước nội dung (áp dụng toàn server)")
    async def alonametoggle_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            async with self._config_lock:
                config = await load_tts_config()
                read_name = config.setdefault("read_name", {})
                guild_id = str(interaction.guild.id)
                read_name[guild_id] = not read_name.get(guild_id, True)
                await save_tts_config(config)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể cập nhật cấu hình: `{error}`", ephemeral=True)
        state = "BẬT ✅" if read_name[guild_id] else "TẮT ❌"
        await interaction.edit_original_response(
            content=f"🔊 Đọc tên người gửi: **{state}** (áp dụng cho toàn bộ server)"
        )

    @app_commands.command(name="alo", description="Gửi TTS vào 1 voice channel cụ thể mà không cần đang đứng trong đó")
    @app_commands.describe(voice="Voice channel bot đang có mặt", noi_dung="Nội dung muốn đọc")
    async def alo_cmd(self, interaction: discord.Interaction, voice: discord.VoiceChannel, noi_dung: str):
        guild = interaction.guild
        voice_client = guild.voice_client
        if not voice_client or voice_client.channel.id != voice.id:
            return await interaction.response.send_message(
                f"❌ Bot chưa vào voice **{voice.name}**! Dùng `/alojoin` trước.", ephemeral=True
            )
        if self.mute_state.get(guild.id):
            return await interaction.response.send_message(
                "🔇 Bot đang bị mute ở voice này, dùng `/alounmute` trước.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        try:
            await self.enqueue_tts(guild, noi_dung.strip(), interaction.user.display_name, voice.id)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể đọc cấu hình TTS: `{error}`", ephemeral=True)
        await interaction.edit_original_response(content=f"📢 Đã gửi vào hàng chờ đọc ở **{voice.name}**!")

    @app_commands.command(name="aloconfig", description="Bật/tắt bot tự động ở lại voice (khi rớt mạng hoặc restart) — Officer")
    @app_commands.describe(rejoin="Bật/tắt tự động rejoin", voice="Voice channel cần config (mặc định = voice bot đang ở)")
    @app_commands.choices(rejoin=[
        app_commands.Choice(name="Bật", value="on"),
        app_commands.Choice(name="Tắt", value="off"),
    ])
    async def aloconfig_cmd(self, interaction: discord.Interaction, rejoin: app_commands.Choice[str], voice: discord.VoiceChannel = None):
        if not is_officer(interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)

        target_channel = voice
        if not target_channel:
            voice_client = interaction.guild.voice_client
            if not voice_client:
                return await interaction.response.send_message("❌ Bot chưa ở voice nào, vui lòng chỉ định `voice:`!", ephemeral=True)
            target_channel = voice_client.channel

        await interaction.response.defer(ephemeral=True)
        try:
            async with self._config_lock:
                config = await load_tts_config()
                rejoin_config = config.setdefault("rejoin", {})
                rejoin_config[str(target_channel.id)] = rejoin.value == "on"
                await save_tts_config(config)
        except Exception as error:
            return await interaction.followup.send(f"❌ Không thể cập nhật cấu hình: `{error}`", ephemeral=True)
        state = "BẬT ✅" if rejoin.value == "on" else "TẮT ❌"
        await interaction.edit_original_response(
            content=f"⚙️ Tự động rejoin cho **{target_channel.name}**: **{state}**"
        )


    @app_commands.command(name="alomute", description="Tạm tắt tiếng đọc TTS ở voice hiện tại (bot vẫn ở lại)")
    async def alomute_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild.voice_client:
            return await interaction.response.send_message("❌ Bot không ở voice nào cả!", ephemeral=True)
        self.mute_state[guild.id] = True
        await interaction.response.send_message("🔇 Đã tắt tiếng đọc TTS (bot vẫn ở lại voice).", ephemeral=True)

    @app_commands.command(name="alounmute", description="Bật lại tiếng đọc TTS ở voice hiện tại")
    async def alounmute_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild.voice_client:
            return await interaction.response.send_message("❌ Bot không ở voice nào cả!", ephemeral=True)
        self.mute_state[guild.id] = False
        await interaction.response.send_message("🔊 Đã bật lại tiếng đọc TTS.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AloTtsCog(bot))

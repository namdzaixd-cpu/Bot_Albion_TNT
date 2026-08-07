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
from core.database import execute

# ==============================================================================
# HỆ THỐNG TTS VOICE "ALO" (Bot join voice, đọc chat bằng giọng Google TTS)
# ==============================================================================

MENTION_RE = re.compile(r"<@!?(\d+)>")
CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
CUSTOM_EMOJI_RE = re.compile(r"<a?:(\w+):\d+>")
URL_RE = re.compile(r"https?://\S+")


def load_tts_config():
    data = {"read_name": {}, "rejoin": {}}
    try:
        resp, err = execute(lambda c: c.table("alo_tts_config").select("*").eq("id", 1))
        if err:
            print(f"Error loading alo_tts_config: {err}")
        elif resp and resp.data:
            row = resp.data[0]
            data["read_name"] = row.get("read_name", {})
            data["rejoin"] = row.get("rejoin", {})
    except Exception as e:
        print(f"Error loading alo_tts_config from Supabase: {e}")
    return data


def save_tts_config(data):
    try:
        record = {
            "id": 1,
            "read_name": data.get("read_name", {}),
            "rejoin": data.get("rejoin", {})
        }
        _, err = execute(lambda c: c.table("alo_tts_config").upsert(record))
        if err:
            print(f"Error saving alo_tts_config: {err}")
    except Exception as e:
        print(f"Error saving alo_tts_config to Supabase: {e}")


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

    async def enqueue_tts(self, guild: discord.Guild, text: str, author_name: str):
        if not text or not text.strip():
            return
        gid = guild.id
        config = load_tts_config()
        # Áp dụng chung cho toàn bộ server (guild)
        read_name = config.get("read_name", {}).get(str(gid), True)
        full_text = f"{author_name} nói: {text}" if read_name else text

        if gid not in self.tts_queues:
            self.tts_queues[gid] = asyncio.Queue()
        await self.tts_queues[gid].put(full_text)

        if gid not in self.tts_workers or self.tts_workers[gid].done():
            self.tts_workers[gid] = self.bot.loop.create_task(self._tts_worker(gid))

    async def _tts_worker(self, guild_id):
        queue = self.tts_queues[guild_id]
        while not queue.empty():
            text = await queue.get()
            if self.mute_state.get(guild_id):
                continue
            session = self.voice_sessions.get(guild_id)
            if not session:
                continue
            guild = self.bot.get_guild(guild_id)
            vc = guild.voice_client if guild else None
            if not vc or not vc.is_connected():
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
                # Giới hạn tối đa 1 phút/đoạn bằng option ffmpeg "-t 60"
                vc.play(discord.FFmpegPCMAudio(path, options="-t 60"), after=after_play)
                await finished.wait()
            except Exception as e:
                print(f"❌ [ALO-TTS] Lỗi phát audio: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild and isinstance(message.channel, discord.VoiceChannel) and not message.content.startswith(("!", ".")):
            session = self.voice_sessions.get(message.guild.id)
            if session and session.get("channel_id") == message.channel.id:
                text = clean_text_for_tts(message)
                if text:
                    await self.enqueue_tts(message.guild, text, message.author.display_name)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Xử lý tự động rejoin khi bot bị kick khỏi voice / rớt mạng."""
        if member.id != self.bot.user.id:
            return
        guild = member.guild

        if before.channel is not None and after.channel is None:
            session = self.voice_sessions.get(guild.id)
            if session and session.get("intentional_leave"):
                self.voice_sessions.pop(guild.id, None)
                self.mute_state.pop(guild.id, None)
                return

            channel_id = before.channel.id
            rejoin_cfg = load_tts_config().get("rejoin", {})
            if rejoin_cfg.get(str(channel_id)):
                await asyncio.sleep(3)
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.connect()
                        self.voice_sessions[guild.id] = {"channel_id": channel.id, "intentional_leave": False}
                        print(f"🔄 [ALO] Đã tự rejoin lại {channel.name}")
                    except Exception as e:
                        print(f"⚠️ [ALO] Rejoin thất bại: {e}")
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
        config = load_tts_config()
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
        await vc.disconnect()
        self.voice_sessions.pop(guild.id, None)
        self.mute_state.pop(guild.id, None)
        await interaction.response.send_message(f"👋 Bot đã rời **{channel_name}**.", ephemeral=True)

    @app_commands.command(name="alonametoggle", description="Bật/tắt đọc tên người gửi trước nội dung (áp dụng toàn server)")
    async def alonametoggle_cmd(self, interaction: discord.Interaction):
        config = load_tts_config()
        read_name_cfg = config.setdefault("read_name", {})
        gid = str(interaction.guild.id)
        current = read_name_cfg.get(gid, True)
        read_name_cfg[gid] = not current
        save_tts_config(config)
        state = "BẬT ✅" if read_name_cfg[gid] else "TẮT ❌"
        await interaction.response.send_message(f"🔊 Đọc tên người gửi: **{state}** (áp dụng cho toàn bộ server)", ephemeral=True)

    @app_commands.command(name="alo", description="Gửi TTS vào 1 voice channel cụ thể mà không cần đang đứng trong đó")
    @app_commands.describe(voice="Voice channel bot đang có mặt", noi_dung="Nội dung muốn đọc")
    async def alo_cmd(self, interaction: discord.Interaction, voice: discord.VoiceChannel, noi_dung: str):
        guild = interaction.guild
        vc = guild.voice_client
        if not vc or vc.channel.id != voice.id:
            return await interaction.response.send_message(f"❌ Bot chưa vào voice **{voice.name}**! Dùng `/alojoin` trước.", ephemeral=True)
        if self.mute_state.get(guild.id):
            return await interaction.response.send_message("🔇 Bot đang bị mute ở voice này, dùng `/alounmute` trước.", ephemeral=True)

        await self.enqueue_tts(guild, noi_dung.strip(), interaction.user.display_name)
        await interaction.response.send_message(f"📢 Đã gửi vào hàng chờ đọc ở **{voice.name}**!", ephemeral=True)

    @app_commands.command(name="aloconfig", description="Bật/tắt bot tự động ở lại voice này: khi bị kick/rớt mạng VÀ khi bot restart (redeploy) (Officer only)")
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
            vc = interaction.guild.voice_client
            if not vc:
                return await interaction.response.send_message("❌ Bot chưa ở voice nào, vui lòng chỉ định `voice:`!", ephemeral=True)
            target_channel = vc.channel

        config = load_tts_config()
        rejoin_cfg = config.setdefault("rejoin", {})
        rejoin_cfg[str(target_channel.id)] = (rejoin.value == "on")
        save_tts_config(config)
        state = "BẬT ✅" if rejoin.value == "on" else "TẮT ❌"
        await interaction.response.send_message(f"⚙️ Tự động rejoin cho **{target_channel.name}**: **{state}**", ephemeral=True)

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

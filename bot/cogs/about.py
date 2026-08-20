import discord
from discord import app_commands
from discord.ext import commands

# ==============================================================================
# GIỚI THIỆU BOT
# ==============================================================================
WEBSITE_URL = "https://bot-albion-tnc.onrender.com/"

# ==============================================================================
# LƯU Ý CHO DEV/AI: Mỗi khi code thêm tính năng/lệnh mới, BẮT BUỘC phải 
# cập nhật danh sách FEATURE_FIELDS này để lệnh /aboutme luôn chính xác.
# ==============================================================================
FEATURE_FIELDS = [
    (
        "💎 Siphoned Points",
        "`/spupdate` (cập nhật log siphoned)\n"
        "`/spcheck` (xem bảng xếp hạng tổng tích lũy)\n"
        "`/sphistory` (lịch sử đóng góp của 1 thành viên)\n"
        "`/sptop` (bảng xếp hạng theo thời gian)\n"
        "`/splog` (audit log upload — Officer)\n"
        "`/spexport` (xuất file dữ liệu SP — Officer)\n"
        "`/addsp` (cộng điểm tay — Officer)\n"
        "`/removesp` (trừ điểm tay — Officer)\n"
        "`/removesprole` (xóa thành viên khỏi bảng — Officer)\n"
        "`/resetsp` (reset toàn bộ bảng — Officer)",
    ),
    (
        "⚔️ Massing",
        "`/massing` (tạo party PVP/PVE)\n"
        "`/masstemplatelist` (xem danh sách template)\n"
        "`/masstemplatedelete` (xóa template — Officer)",
    ),
    (
        "🛡️ GuildCheck",
        "`/guildconfig` (cấu hình GuildCheck — Officer)\n"
        "`/guildcheck` (check tay rời guild — Officer)\n"
        "`/unresolved` (xem danh sách chưa xác định — Officer)\n"
        "`/newmembers [days]` (liệt kê thành viên mới vào guild trong N ngày — dùng Discord API, 0đ)",
    ),
    (
        "🔊 Alo (TTS)",
        "`/alojoin` (bot vào voice)\n"
        "`/aloleave` (bot rời voice)\n"
        "`/alonametoggle` (bật/tắt đọc tên người gửi)\n"
        "`/alo` (gửi TTS vào voice chỉ định)\n"
        "`/aloconfig` (cấu hình auto-rejoin — Officer)\n"
        "`/alomute` (tắt tiếng tạm thời)\n"
        "`/alounmute` (bật tiếng lại)",
    ),
    (
        "💰 Core-Bank",
        "`/coresetup` (cài đặt kênh — Officer)\n"
        "`/coreadd` (thêm emoji core — Officer)\n"
        "`/coreremove` (xóa emoji core — Officer)\n"
        "`/coreautoreact` (bật/tắt auto-react — Officer)\n"
        "`/corelist` (xem danh sách core)",
    ),
    (
        "🧠 AI Chatbot",
        "🤖 Bot AI chạy trên **bot riêng** — tag bot AI trong kênh để chat\n"
        "Xoay vòng Ollama/Gemini/OpenRouter, hỗ trợ vision, tóm tắt kênh, RAG library\n"
        "⚡ Failover 8 step, cache tóm tắt 10p, timeout 6s — phản hồi nhanh, 0đ",
    ),
    (
        "👋 Onboarding",
        "`/recuibot setup_channels` (tạo bộ kênh tiếp đón — Officer)\n"
        "`/recuibot set_apply_channel` (chọn kênh apply — Officer)\n"
        "`/recuibot setup_roles` (cài đặt role — Officer)\n"
        "`/recuibot toggle` (bật/tắt tính năng Onboarding — Officer)\n"
        "`/recuibot list` (xem cấu hình & đơn chờ duyệt — Officer)",
    ),
]


class AboutCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="aboutme", description="Giới thiệu về TNC Manager Bot")
    async def aboutme_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ TNC Manager",
            description=(
                "Bot quản lý Guild **TNC** trong Albion Online.\n\n"
                "🏆 **Credits & Tác giả:**\n"
                "🔹 **N4MDZ4I**: Phát triển nền tảng và các tính năng cốt lõi (Massing, Siphoned...)\n"
                "🔹 **Kudo2ten**: Phát triển mảng Chat AI\n"
                "🔹 **Twot**: Tối ưu & hoàn thiện hệ thống\n\n"
                f"🌐 [Trang giới thiệu]({WEBSITE_URL})"
            ),
            color=0x3498db,
        )
        for name, value in FEATURE_FIELDS:
            embed.add_field(name=name, value=value, inline=False)
            

        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        elif self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AboutCog(bot))

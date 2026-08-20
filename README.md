# TNC Manager — Albion Online Guild Discord Bot

Discord bot quản lý guild **TNC** trong game Albion Online. Bot chính viết bằng Python
(`discord.py`), được host online tại [bot-albion-tnc.onrender.com](https://bot-albion-tnc.onrender.com/), kèm một dashboard web
viết bằng Next.js trong `web_dashboard/`.

## Cấu trúc dự án

```
bot/                  Discord bot Python (thành phần chính, đang chạy production)
  main.py             Entry point: khởi tạo bot, load các cog, chạy keep_alive + bot.run
  core/               Hạ tầng dùng chung: config (env/const), storage (đọc/ghi JSON),
                      permissions (is_officer), webserver (Flask keep-alive)
  cogs/               Mỗi hệ thống tính năng là 1 Cog: about, siphoned, massing, lastseen,
                      guildcheck, alo_tts, corebank, onboarding, sync
  *.json              Dữ liệu bot (điểm SP, massing, register, config...), tự backup .bak
web_dashboard/        Dashboard web Next.js (Discord OAuth2)

# Tách repo: AI Chatbot → https://github.com/kudominer/TNC-Chatbot (deploy Render tài khoản riêng)
```

## Bot Discord — tính năng

| Hệ thống | Lệnh | Mô tả |
|---|---|---|
| **About** | `/aboutme` | Giới thiệu bot + link trang web (embed ngắn gọn) |
| **Onboarding** | `/recuibot setup_channels`, `/recuibot set_apply_channel`, `/recuibot setup_roles`, `/recuibot toggle`, `/recuibot list` | Hệ thống Bot Thư Ký tiếp đón thành viên mới, duyệt đơn qua Forum, `/recuibot list` xem cấu hình & đơn chờ |
| **Siphoned Points** | `/spupdate`, `/spcheck`, `!addsp`, `!removesp`, `!removesprole`, `!resetsp` | Parse file log `.txt` để cộng dồn điểm siphoned theo người chơi, bảng xếp hạng phân trang |
| **Massing** | `/massing`, `/masstemplatelist`, `/masstemplatedelete` | Tạo party PVP/PVE theo role/weapon, UI nút bấm (join/kick/move/fill), lưu template, tự khôi phục sau restart |
| **GuildCheck** | `/registertnc`, `/registerfor`, `/myign`, `/guildconfig`, `/guildcheck`, `/unresolved`, `/newmembers [days]` | Đăng ký IGN Albion, tự kiểm tra qua Albion API xem còn trong guild không, tự xóa role nếu đã rời, `/newmembers` liệt kê member mới vào guild qua Discord API (0đ) |
| **Alo (TTS)** | `/alojoin`, `/aloleave`, `/alonametoggle`, `/alo`, `/aloconfig`, `/alomute`, `/alounmute` | Đọc tin nhắn text thành giọng nói (gTTS) vào voice channel, tự rejoin khi rớt mạng |
| **Core-Bank** | `/coresetup`, `/coreadd`, `/coreremove`, `/coreautoreact`, `/corelist` | Tự động thả emoji reaction lên ảnh core nộp vào kênh, quy đổi ra giá trị silver |
| **AI Chatbot** | _(chạy trên bot riêng — xem [TNC-Chatbot](https://github.com/kudominer/TNC-Chatbot))_ | Tag bot AI để chat, `/wiki`, `/iteminfo`, tóm tắt kênh, learning |

Phân quyền dựa theo **tên role Discord**: `officer`, `guild master`, `admin`, `phó hội`, `chủ hội`.

## AI Chatbot (tách repo riêng)

Tính năng AI Chat đã được tách sang repo **[TNC-Chatbot](https://github.com/kudominer/TNC-Chatbot)** và deploy trên Render tài khoản riêng.

- Chatbot chạy Discord bot riêng (token riêng), cùng guild
- Dashboard gửi webhook reload đến cả 2 bot khi config thay đổi
- Chi tiết: xem README trong repo TNC-Chatbot

## Lưu trữ dữ liệu

Toàn bộ state lưu dưới dạng file JSON phẳng trong `bot/`. Mỗi lần ghi:

1. Ghi ra file `.tmp`, backup file cũ thành `.bak`, rồi `os.replace` — chống hỏng dữ liệu khi crash giữa chừng.
2. Tự động `git commit` + `git push` dữ liệu lên GitHub (do Replit không có disk bền vững) — xem `sync_to_github()` trong `bot/main.py`.

## Chạy bot

```bash
pip install -r requirements.txt
# hoặc: uv sync (dùng pyproject.toml / uv.lock)

cp bot/.env.example bot/.env   # rồi điền giá trị thật
python bot/main.py
```

Biến môi trường cần thiết (xem [bot/.env.example](bot/.env.example)):

| Biến | Mô tả |
|---|---|
| `DISCORD_TOKEN` | Token bot Discord |
| `DISCORD_GUILD_ID` | ID server Discord |
| `GITHUB_GIT_URL` | URL GitHub kèm Personal Access Token, dùng để auto-sync dữ liệu |
| `OPENROUTER_API_KEY` | API key OpenRouter, dùng cho tính năng chat AI (cog `chat_ai`) |
| `GEMINI_API_KEY` | API key Google AI Studio, dùng cho các bước Gemini trong chuỗi dự phòng AI |
| `OLLAMA_API_KEY` | API key Ollama Cloud (`ollama.com`), dùng cho các bước Ollama trong chuỗi dự phòng AI (tùy chọn, một số endpoint không bắt buộc) |

Bot expose Flask server tại `http://localhost:5000` (Online: [bot-albion-tnc.onrender.com](https://bot-albion-tnc.onrender.com/)):
- `GET /` — Trang giới thiệu & trạng thái bot (HTML)
- `GET /health` — health check

## Lưu ý bảo mật

- **Không bao giờ commit file `.env`** — chứa `DISCORD_TOKEN` và `GITHUB_GIT_URL` (URL này nhúng
  sẵn PAT của GitHub).
- `GITHUB_GIT_URL` được truyền trực tiếp vào `subprocess.run(["git", "push", GIT_URL, "main"])` —
  cẩn thận khi log lỗi vì URL có thể lộ token ra console/log.

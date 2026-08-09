# TNC Manager — Albion Online Guild Discord Bot

Discord bot quản lý guild **TNC** trong game Albion Online. Bot chính viết bằng Python
(`discord.py`), được host online tại [bot-albion-tnc.onrender.com](https://bot-albion-tnc.onrender.com/), kèm một dashboard web
viết bằng Next.js trong `web_dashboard/`.

## Cấu trúc dự án

```
bot/                  Discord bot Python (thành phần chính, đang chạy production)
  main.py             Entry point: khởi tạo bot, load các cog, chạy keep_alive + bot.run
  core/               Hạ tầng dùng chung: config (env/const), storage (đọc/ghi JSON + sync GitHub),
                      permissions (is_officer), webserver (Flask keep-alive)
    templates/        Templates dùng chung: trạng thái web (index.html), mô tả tính cách AI (chat_ai_instruction.txt)
  cogs/               Mỗi hệ thống tính năng là 1 Cog: about, siphoned, massing, lastseen,
                      guildcheck, alo_tts, corebank
  *.json              Dữ liệu bot (điểm SP, massing, register, config...), tự backup .bak
web_dashboard/        Dashboard web Next.js (Discord OAuth2)
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
| **Chat AI** | Tag bot / reply bot, `/aimodel balance`, `/wiki`, `/iteminfo`, tóm tắt kênh | Chat AI theo tính cách tùy chỉnh (xem [Cấu hình AI Chat](#cấu-hình-ai-chat)), đọc context kênh/link/reply, **tự động tóm tắt kênh từ lịch sử Supabase** (gõ "tóm tắt kênh <tên> từ <tối hôm qua/hôm nay/tuần này>"), **tự động trả câu hỏi về item trang bị** (vũ khí/giáp/skill/passive) từ database Albion offline bằng tiếng Việt, **tối ưu 0đ**: cache db 6h + cache summary 10p + debounce 8s + tiền xử lý giảm 60% token + ưu tiên model 128k cho tóm tắt dài + timeout failover 6s, tự xoay vòng qua 3 nhà cung cấp (Ollama/Gemini/OpenRouter) khi bên nào lỗi |

Phân quyền dựa theo **tên role Discord**: `officer`, `guild master`, `admin`, `phó hội`, `chủ hội`.
## Cấu hình AI Chat

Cog `chat_ai` gọi lần lượt qua **3 nhà cung cấp** (Ollama, Google Gemini, OpenRouter) theo 1 chuỗi dự phòng cố định — không cần chọn model thủ công. Mỗi tin nhắn, bot thử từng bước theo thứ tự, bước nào lỗi (không phải HTTP 200, timeout, hoặc JSON không parse được) thì tự chuyển ngay bước kế tiếp:

1. Ollama — `minimax-m3`
2. Google Gemini — `gemini-3.5-flash-lite`
3. OpenRouter — `nvidia/nemotron-3-ultra-550b-a55b:free`
4. Google Gemini — `gemini-3.1-flash-lite`
5. OpenRouter — `inclusionai/ling-3.0-flash:free`
6. Google Gemini — `gemini-2.5-flash`
7. Ollama — `gpt-oss:120b`
8. OpenRouter — `openrouter/free`

Chuỗi này khai báo trong hằng số `FAILOVER_CHAIN` ở đầu file `bot/cogs/chat_ai.py` (đổi thứ tự/model thì sửa trực tiếp code, không có lệnh Discord để chỉnh).

- **Timeout mỗi bước**: 10 giây (`FAILOVER_STEP_TIMEOUT`) — quá thời gian này coi như lỗi và chuyển bước kế.
- **Đóng băng bước lỗi**: bước nào vừa lỗi sẽ bị bỏ qua trong 5 phút (`FAILOVER_FREEZE_SECONDS`) để tránh chờ timeout lặp lại ở tin nhắn sau; nếu tất cả các bước đều đang đóng băng thì bot bỏ qua đóng băng và thử lại toàn bộ chuỗi.
- **Vision (đọc ảnh)**: 2 model Ollama không hỗ trợ ảnh — nếu tin nhắn có đính kèm ảnh, bước Ollama sẽ tự bị bỏ qua trong lần thử đó.
- **Tính cách bot**: sửa trực tiếp file text [bot/core/templates/chat_ai_instruction.txt](bot/core/templates/chat_ai_instruction.txt) — không cần đụng code. Bot tự đọc file này lúc khởi động, nên sửa xong phải **restart bot** mới áp dụng. File có placeholder `{CURRENT_MODEL}` được tự động thay bằng tên model của bước đang thử. Nếu file trống hoặc bị xóa, bot fallback về cấu hình mặc định khai báo trong `chat_ai.py`.
- **Kiểm tra số dư OpenRouter**: `/aimodel balance` (không cần quyền Officer).

### Test AI chat ngoài Discord

Bộ script độc lập trong [test_api_key/](test_api_key/README.md), cùng lấy API key từ `.env` qua `core/config.py` (đổi model/key ở `.env` thì cả script lẫn bot chính đều dùng chung giá trị mới):

| File | Công dụng |
|---|---|
| `test_api_key/test_api_full_with_instruction.py` | Gộp cả 3 nhà cung cấp (13 model), gọi kèm system instruction thật từ `chat_ai_instruction.txt` — mô phỏng đúng điều kiện production |
| `test_api_key/test_api_full.py` | Gộp cả 3 nhà cung cấp (13 model), gọi trần không có system instruction — đo độ trễ gốc của API/model, dùng để so sánh xem prompt tính cách có làm chậm phản hồi hay không |
| `test_api_key/test_gemini.py`, `test_ollama.py`, `test_openrouter.py` | Test riêng lẻ từng nhà cung cấp |

```bash
python3 test_api_key/test_api_full_with_instruction.py
python3 test_api_key/test_api_full.py
```

Gõ câu hỏi rồi Enter, script in ra `[X.XXs] <câu trả lời>` — số giây là thời gian phản hồi thật từ API, không qua Discord.

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

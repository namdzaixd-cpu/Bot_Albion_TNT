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
| **Siphoned Points** | `/spupdate`, `/spcheck`, `/sphistory`, `/sptop`, `/splog`, `/spexport`, `/addsp`, `/removesp`, `/removesprole`, `/resetsp` | Import log `.txt` atomic, cộng dồn điểm, lịch sử và xếp hạng theo khoảng thời gian |
| **Massing** | `/massing`, `/masstemplatelist`, `/masstemplatedelete` | Tạo party PVP/PVE theo role/weapon, UI nút bấm (join/kick/move/fill), lưu template, tự khôi phục sau restart |
| **GuildCheck** | `/guildconfig`, `/guildcheck`, `/guildmembers`, `/guildaudit`, `/newmembers [days]` | Cấu hình guild, tra cứu thành viên in-game, hiển thị bảng phân trang thành viên guild & fame, đối soát nhân sự In-game vs Discord, `/newmembers` lọc thành viên mới vào guild qua Discord API (0đ) |
| **Alo (TTS)** | `/alojoin`, `/aloleave`, `/alonametoggle`, `/alo`, `/aloconfig`, `/alomute`, `/alounmute` | Đọc tin nhắn text thành giọng nói (gTTS) vào voice channel, tự rejoin khi rớt mạng |
| **Core-Bank** | `/coresetup`, `/coreadd`, `/coreremove`, `/coreautoreact`, `/corelist` | Tự động thả emoji reaction lên ảnh core nộp vào kênh, quy đổi ra giá trị silver |
| **Update Translator** | `/utconfig`, `/utstatus` | Tự tạo thread cho mỗi tin mới trong kênh `#update`, AI đặt tiêu đề + dịch sang tiếng Việt (Gemini), react 🇻🇳 để dịch lại tin cũ |
| **AI Chatbot** | _(chạy trên bot riêng — xem [TNC-Chatbot](https://github.com/kudominer/TNC-Chatbot))_ | Tag bot AI để chat, `/wiki`, `/iteminfo`, tóm tắt kênh, learning |

Phân quyền dựa theo **tên role Discord**: `officer`, `guild master`, `admin`, `phó hội`, `chủ hội`.

## AI Chatbot (tách repo riêng)

Tính năng AI Chat đã được tách sang repo **[TNC-Chatbot](https://github.com/kudominer/TNC-Chatbot)** và deploy trên Render tài khoản riêng.

- Chatbot chạy Discord bot riêng (token riêng), cùng guild
- Dashboard gửi webhook reload đến cả 2 bot khi config thay đổi
- Chi tiết: xem README trong repo TNC-Chatbot

## Lưu trữ dữ liệu

Dữ liệu vận hành lưu trên Supabase: party/templates/GuildCheck/heartbeat ở `json_storage`,
SP/CoreBank/LastSeen/config ở các bảng chuyên biệt. `bot/Storage/` là legacy, không GitHub sync.

- Runtime dùng async DB/storage boundary; DB lỗi không bị hiểu là state rỗng.
- SP economy/history/watermark commit atomic; Core payment ledger giữ kết quả chưa rõ để đối soát,
  không tự retry API ngoài khi có khả năng đã cộng/trừ tiền.
- Chi tiết schema, migration và rollout: [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md).

## Triển khai bot

```bash
pip install -r requirements.txt
# Cấu hình environment trên Render theo .env.example; không ghi đè .env đang có.
# Apply schema/migrations tới DB được chọn có chủ đích trước deploy code phụ thuộc RPC.
python scripts/apply_schema.py
```

Entry point production: `bot/main.py`. **Không chạy thêm bot thật trên local** khi production đang
hoạt động, tránh trùng Discord gateway. Dev chỉ chạy tests/smoke cô lập, không dùng dữ liệu thật.

Biến môi trường backend (xem [.env.example](.env.example)):

| Biến | Mô tả |
|---|---|
| `DISCORD_TOKEN` | Token bot Discord |
| `DISCORD_GUILD_ID` | ID server Discord |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Key backend; không đưa ra browser |
| `WEBHOOK_SECRET` | Secret server-side giống dashboard để xác thực reload |
| `DATABASE_URL` / `DIRECT_URL` | Kết nối PostgreSQL cho migration; không log password |
| `GEMINI_API_KEY` | API key cho Update Translator; AI chatbot nằm ở repo riêng |

Bot expose Flask server tại `http://localhost:5000` (Online: [bot-albion-tnc.onrender.com](https://bot-albion-tnc.onrender.com/)):
- `GET /` — Trang giới thiệu; HTTP service sống không chứng minh Discord gateway ready
- `POST /api/webhook/reload` — Yêu cầu `Authorization: Bearer <WEBHOOK_SECRET>`

Dashboard `/api/bot-status` trả `main_bot` và `chatbot`, lấy heartbeat readiness/freshness từ DB.

## Kiểm tra trước khi push

CI dùng Python 3.11. Trong môi trường phát triển cô lập, cài `requirements.txt` và `pytest`, rồi
chạy từ thư mục gốc:

```bash
python -m compileall -q bot
pytest bot/tests -v
```

CI chạy `pytest tests -v` từ `bot/`. `pytest.ini` cấu hình `pythonpath = . bot` để cả hai cách
chạy đều import được module ở thư mục gốc (như `test_api_key/`) và trong `bot/`.

## Lưu ý bảo mật

- Không commit `.env`, DB credential, Discord token hoặc bank token. Dashboard trả
  `token_configured`, không trả raw bank token; admin đổi token qua PATCH server-side.
- Thiếu/sai webhook secret không dispatch reload. Persist thành công nhưng reload lỗi được báo
  rõ là chưa áp dụng, không báo success giả.
- Credential từng hard-code cần rotate qua quyền quản trị provider nếu còn hiệu lực;
  xóa literal trong source không thu hồi credential đã lộ.

## Toàn vẹn dữ liệu và đối soát

- [Ledger CoreBank, SP transaction, runtime/reload và rollout](docs/features/data_integrity_and_runtime.md).
- [Ma trận sửa F01–F36 và trạng thái vận hành](docs/tasks/2026-10-04_full_project_fixes/02_task.md).
- [Bằng chứng kiểm chứng cô lập và giới hạn production](docs/tasks/2026-10-04_full_project_fixes/03_walkthrough.md).

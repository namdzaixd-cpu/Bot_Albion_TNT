# Discord bot TNC

Entry point production: `bot/main.py`, dùng `discord.py` và Flask. Bot thật chạy trên Render; không chạy thêm bản local để test.

Cấu hình: `DISCORD_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_URL`, backend `SUPABASE_SERVICE_ROLE_KEY`, và `WEBHOOK_SECRET` giống dashboard. Gemini key cần cho Update Translator. Xem `../.env.example` và `../README.md` cho danh sách lệnh hiện tại.

Runtime DB I/O dùng async boundary; config/state được load trong lifecycle async, không query trong constructor. Storage lỗi không dùng empty default; persist lỗi không báo success.

## HTTP và trạng thái

- `GET /`: HTML giới thiệu dự án. HTTP thành công chỉ chứng minh web service phản hồi.
- `POST /api/webhook/reload`: yêu cầu `Authorization: Bearer <WEBHOOK_SECRET>`; thiếu cấu hình/sai secret không dispatch.
- Heartbeat `tnc_bot_status.json` phản ánh Discord gateway readiness. Dashboard `/api/bot-status` trả `main_bot`/`chatbot` và kiểm tra freshness.

Không có các lệnh demo `/ping` hoặc `/hello`, endpoint JSON root hay `/health` trong contract hiện tại.

## Kiểm chứng an toàn

```bash
python -m pytest bot/tests -q
```

Test harness chặn dotenv và outbound network trước import, sử dụng fake credentials/integrations. Không chạy tests/helper kết nối thật bằng credential production. Database schema và rollout xem `../DATABASE_ARCHITECTURE.md`.

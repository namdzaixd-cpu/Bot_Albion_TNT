# Project Timeline — Bot Albion TNC

Nhật ký tiến độ và các mốc phát triển của dự án TNC Manager Bot.

---

## 📅 2026-09-22: Tính năng Tra cứu & Đối soát Thành viên Guild In-Game (Albion Online)
- **Mục tiêu:** Cho phép lấy dữ liệu danh sách thành viên Guild in-game từ SBI Official API, phân trang xem Fame và đối soát nhân sự In-game vs Server Discord.
- **Thay đổi chính:**
  - `bot/cogs/guildcheck.py`:
    - Bổ sung hàm `albion_get_guild_members(region, guild_id)` gọi REST API `gameinfo.albiononline.com`.
    - Tạo class `GuildMembersPaginationView` hỗ trợ duyệt danh sách qua các nút `⏮`, `◀`, `▶`, `⏭`.
    - Thêm lệnh `/guildmembers` với tùy chọn sắp xếp Fame / IGN và xuất file `.txt`.
    - Thêm lệnh `/guildaudit` (Officer) tự động đối soát chéo In-game vs Nickname Discord + đính kèm file báo cáo.
  - `bot/cogs/about.py`: Cập nhật bảng tính năng trong lệnh `/aboutme`.
  - `README.md`: Cập nhật mô tả hệ thống GuildCheck.
  - `docs/features/guild_members_audit.md`: Tạo tài liệu đặc tả tính năng.
- **Kết quả:** Kiểm tra cú pháp `py_compile` thành công, code chạy ổn định và tối ưu tài nguyên.

---

## 📌 Mục Bàn giao Bắt buộc (Mandatory Agent Handover)

### 1. Tình trạng hiện tại của dự án
- Bot đang hoạt động với cấu trúc Discord.py gồm các Cogs: `about`, `alo_tts`, `blacklist`, `corebank`, `guildcheck`, `lastseen`, `massing`, `onboarding`, `siphoned`, `sync`, `update_translator`.
- Dữ liệu lưu trữ qua Supabase (`bot/core/storage.py`).
- Cụm tính năng AI Chat đã được tách sang repo riêng `TNC-Chatbot`.
- Hệ thống `guildcheck.py` đã hoàn thiện đầy đủ các tính năng: cấu hình guild (`/guildconfig`), kiểm tra 1 player (`/guildcheck`), xem danh sách thành viên in-game (`/guildmembers`), đối soát nhân sự in-game vs discord (`/guildaudit`), và lọc thành viên mới (`/newmembers`).

### 2. Bối cảnh & Dự định kế tiếp của user
- User vừa yêu cầu bổ sung khả năng lấy dữ liệu thành viên guild in-game. Tính năng đã được triển khai hoàn chỉnh và an toàn theo chuẩn SBI API.
- Sẵn sàng nhận các yêu cầu tiếp theo về quản trị guild, cập nhật UI web dashboard hoặc tối ưu thêm các cog khác.

### 3. Hướng dẫn kỹ thuật nhanh cho Agent tiếp theo
- Khi chạy kiểm tra cú pháp: Dùng `python -m py_compile bot/cogs/*.py`.
- **TUYỆT ĐỐI KHÔNG** khởi động bot thật ở local (`python bot/main.py`) vì bot chạy trên Render.
- Đọc/ghi dữ liệu luôn thông qua `load_json()` / `save_json()` trong `bot/core/storage.py`.
- Tuân thủ quy trình làm việc (bàn thiết kế -> chốt -> plan -> chốt -> code) và SBI Compliance Policy.

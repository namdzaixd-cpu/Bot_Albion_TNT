# Walkthrough: Quản Lý & Đối Soát Thành Viên Guild In-Game (Albion Online)

## 1. Tóm tắt công việc đã thực hiện
Đã hoàn thiện hệ thống quản lý thành viên Guild in-game kết nối trực tiếp với **Albion Online Official API** (`gameinfo.albiononline.com`), cung cấp các công cụ trực quan và hữu ích cho ban quản trị và thành viên:

1. **Lấy danh sách thành viên In-game (`albion_get_guild_members`):**
   - Kết nối API chính thức SBI theo đúng Region (Asia, Americas, Europe).
   - Định dạng Fame thông minh (`format_fame`: `12.5M`, `450K`).

2. **Lệnh Slash `/guildmembers`:**
   - Xem danh sách thành viên với Embed Discord phân trang (`⏮`, `◀`, `▶`, `⏭`).
   - Tùy chọn sắp xếp theo Kill Fame, Death Fame, Tên IGN (A-Z).
   - Tùy chọn `export_file: True` xuất danh sách đầy đủ ra file text `.txt`.

3. **Lệnh Slash `/guildaudit` (Officer):**
   - Tự động quét và đối soát toàn bộ thành viên trong Guild in-game với danh sách Nickname trên server Discord.
   - Thống kê chi tiết số lượng khớp, số lượng in-game chưa vào Discord hoặc chưa đổi tên.
   - Tự động xuất file text `guild_audit_<guild_name>_<date>.txt` đính kèm.

4. **Đồng bộ Tài liệu & Giới thiệu:**
   - Cập nhật `/aboutme` trong `bot/cogs/about.py`.
   - Cập nhật `README.md`, `docs/features/guild_members_audit.md`, `docs/timeline.md`.

## 2. Kiểm thử & Đảm bảo chất lượng
- Đã chạy kiểm tra cú pháp `python -m py_compile` cho toàn bộ các file Python được chỉnh sửa.
- Hoàn toàn tuân thủ SBI Compliance Policy (Chỉ đọc qua REST API chính thức, không hook, không can thiệp game client).

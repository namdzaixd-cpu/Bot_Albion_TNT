# Plan: Khắc Phục Lỗi Tự Động Phản Hồi & Duyệt Đơn Apply (Onboarding)

## 1. Mục Tiêu & Vấn Đề
- **Hiện tượng:** Khi thành viên mới tạo chủ đề (thread) Apply trong Forum Channel, bot không tự động phản hồi bảng Embed kiểm tra nhân vật.
- **Nguyên nhân chính:**
  1. Thiếu sự kiện `on_thread_create` để bắt kịp thời điểm Forum post được tạo và tự động join thread.
  2. Sự kiện `on_message` bị chặn do `thread.owner_id` chưa kịp nạp vào cache (`None`).
  3. Regex bóc tách `Ingame` và `Năm sinh` bị lỗi khi người dùng copy form có markdown in đậm (`**Ingame:**`).
  4. Lỗi cấp Role/Đổi tên (`guild.get_member` trả về `None` khi chưa nạp cache) và kiểm tra quyền Officer cứng nhắc.

---

## 2. Giải Pháp Triển Khai
1. Thêm `on_thread_create` trong `bot/cogs/onboarding.py` để tự động `thread.join()` và đọc starter message.
2. Nâng cấp Regex trích xuất Ingame & Năm sinh hỗ trợ Markdown bold/dashes/numbering.
3. Thêm hàm `_get_member_or_fetch` fallback qua `guild.fetch_member` khi duyệt Role & Rename.
4. Mở rộng kiểm tra quyền Officer (`check_officer_permission`) chấp nhận Administrator Discord, configured `officer_role_id`, hoặc `is_officer`.
5. Bổ sung unit tests cho Regex markdown và fallback permissions.

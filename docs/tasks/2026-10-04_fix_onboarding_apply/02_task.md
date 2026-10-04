# Task List: Sửa Lỗi Tự Động Phản Hồi & Duyệt Đơn Apply (Onboarding)

- [x] Bổ sung listener `on_thread_create` tự động join thread và xử lý starter message
- [x] Sửa listener `on_message` không chặn khi `thread.owner_id` là `None`
- [x] Nâng cấp Regex trích xuất `Ingame` & `Năm sinh` khớp với mọi định dạng markdown (`**Ingame:**`, `1. Ingame:`, `- Ingame:`)
- [x] Thêm hàm helper `_get_member_or_fetch` fallback qua `guild.fetch_member` khi cấp Role & Rename
- [x] Thêm hàm helper `check_officer_permission` mở rộng kiểm tra Administrator, configured `officer_role_id`, và `is_officer`
- [x] Thêm test cases trong `bot/tests/test_onboarding_logic.py`
- [x] Sửa fallback loopback socket cho asyncio trên Windows trong `bot/tests/conftest.py`
- [x] Kiểm tra cú pháp `py_compile` và chạy pytest toàn diện (64 passed, 1 skipped)
- [x] Cập nhật timeline dự án `docs/timeline.md`

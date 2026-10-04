# Task List - Tự Động Xóa / Dọn Dẹp Bảng Tiến Độ Ephemeral

- [x] Lưu vết `last_interaction` trong `ApplyStep1Modal.on_submit` và `ApplyStep2Modal.on_submit`.
- [x] Thực hiện `delete_original_response()` trên interaction cũ khi user gửi `ApplyStep2Modal` và `ApplyStep3Modal`.
- [x] Thêm task nền `auto_cleanup` tự động xóa tin nhắn hoàn tất 100% sau 60 giây.
- [x] Sửa lỗi cú pháp và chạy `python -m py_compile bot/cogs/onboarding.py`.
- [x] Chạy kiểm tra toàn bộ unit test suite `pytest bot/tests` (66 passed).
- [x] Cập nhật timeline dự án và tài liệu lưu trữ.

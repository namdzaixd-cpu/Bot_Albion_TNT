# Walkthrough - Tự Động Dọn Dẹp Tin Nhắn Ephemeral & Hoàn Tất Luồng Onboarding

## Chi tiết các thay đổi

### 1. `bot/cogs/onboarding.py`
- **Tự động xóa tin nhắn trung gian:**
  - Ở Bước 1: Khi nộp Modal 1/3, bot lưu `last_interaction` vào `draft_applications`.
  - Ở Bước 2: Khi nộp Modal 2/3, bot xóa tin nhắn tiến độ của Bước 1 thông qua `await last_it.delete_original_response()` và lưu interaction Bước 2.
  - Ở Bước 3: Khi nộp Modal 3/3, bot xóa tin nhắn tiến độ của Bước 2 và tiến hành tạo Thread nộp đơn.
- **Tự động thu hồi bảng hoàn tất:**
  - Sau khi gửi tin nhắn hoàn tất 100% kèm hướng dẫn nộp ingame, bot chạy coroutine `auto_cleanup` tự động xóa tin nhắn này sau 60 giây.

## Kết quả kiểm thử
- `python -m py_compile bot/cogs/onboarding.py`: ✅ Thành công không lỗi cú pháp.
- `pytest bot/tests`: ✅ 66 passed, 1 skipped.

# Implementation Plan - Tự Động Xóa / Dọn Dẹp Bảng Tiến Độ Ephemeral Khi Nộp Đơn Onboarding

## 1. Bối cảnh & Mục tiêu
- Khi người dùng nộp đơn theo quy trình 3 bước (1/3 -> 2/3 -> 3/3), các tin nhắn thông báo tiến độ trung gian (Ephemeral messages 33%, 66%, 100%) hiển thị trong khung chat riêng tư của người dùng.
- Sau khi hoàn thành hoặc chuyển bước, các tin nhắn này không còn giá trị và có thể gây rác khung chat hoặc hiển thị "This interaction failed" nếu user nhấn lại.
- **Mục tiêu:** Tự động dọn dẹp / xóa bỏ tin nhắn Ephemeral cũ của các bước trước ngay khi người dùng bước sang bước tiếp theo, và tự động thu hồi tin nhắn hoàn tất 100% sau khi tạo xong Thread nộp đơn.

## 2. Giải pháp kỹ thuật (Phương án 1)
1. **Lưu vết interaction gần nhất:** Trong bộ nhớ tạm `draft_applications[user_id]`, lưu tham chiếu `last_interaction`.
2. **Tự động xóa tin nhắn bước trước:** Khi người dùng gửi Step 2 hoặc Step 3 Modal, gọi `await last_it.delete_original_response()` để xóa sạch bảng tiến độ của bước trước đó.
3. **Thu hồi bảng hoàn tất 100%:** Sau khi tạo xong Thread nộp đơn trong forum/kênh apply và hiển thị bảng hướng dẫn bước tiếp theo (nộp ingame), lên lịch tác vụ nền `auto_cleanup` tự động xóa tin nhắn này sau 60 giây.
4. **Bảo đảm an toàn:** Bọc toàn bộ lệnh xóa trong `try...except Exception: pass` để tránh lỗi khi interaction đã bị đóng hoặc quá hạn 15 phút của Discord.

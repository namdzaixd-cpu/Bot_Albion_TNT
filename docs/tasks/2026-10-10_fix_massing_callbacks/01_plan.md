# Kế hoạch khắc phục lỗi Callback PartyView & Lưu Template Massing

## 1. Vấn đề
- Bảng Party Massing bị mất các hàm callback xử lý nút bấm trong class `PartyView` dẫn đến việc bấm các nút quản trị, xem build, nhận slot, và lưu template không hoạt động.
- Template CTA mặc định chưa được hỗ trợ nạp sẵn trong `active_templates`.

## 2. Giải pháp triển khai
1. Khôi phục toàn bộ các hàm callback trong class `PartyView` (`save_template_callback`, `view_build_callback`, `fill_callback`, `leave_callback`, `add_callback`, `move_callback`, `kick_callback`, `note_callback`, `delete_callback`, `copy_callback`, `ping_callback`, `make_join_callback`).
2. Bổ sung xử lý an toàn cho hàm `view_build_callback` và `make_join_callback` khi gửi hướng dẫn build trang bị.
3. Đảm bảo template mặc định `cta tnc` luôn có sẵn trong bộ nhớ RAM khi khởi động.
4. Bổ sung unit test xác thực sự tồn tại và tính sẵn sàng của các callback trong `PartyView`.

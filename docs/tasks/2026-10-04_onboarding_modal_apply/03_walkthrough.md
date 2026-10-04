# Walkthrough: Quy Trình Nộp Đơn Qua Multi-Step Modal (12 Câu Hỏi)

## 1. Hướng dẫn sử dụng cho Officer
1. Dùng lệnh `/recuibot post_panel` trong kênh tiếp đón (hoặc kênh thông báo apply):
   - Có thể chỉ định `channel: #kenh-tiep-don`, `custom_title: ...`, `custom_desc: ...` nếu muốn.
2. Bot sẽ gửi một Embed thông báo màu vàng kim với nút **`[📝 Nộp Đơn Gia Nhập Guild]`**.

## 2. Trải nghiệm của thành viên mới
1. **Bước 1:** Bấm nút `[📝 Nộp Đơn Gia Nhập Guild]` ➔ Hiện popup điền 5 thông tin cơ bản (IGN, Năm sinh, Giới tính, Quốc gia, Nguồn biết guild).
2. **Bước 2:** Bấm `[👉 Điền tiếp Bước 2 / 3]` ➔ Hiện popup điền 5 thông tin kỹ năng (Thời gian chơi, Mic, Thiết bị, Role yêu thích, Guild cũ).
3. **Bước 3:** Bấm `[📝 Hoàn tất Bước 3 / 3]` ➔ Hiện popup điền 2 thông tin mục tiêu & cam kết (Mục đích vào guild, Đồng ý quy định).
4. Sau khi gửi: Bot tự động tạo Thread mới trong kênh Apply, tag Officer vào duyệt với 3 nút `Accept`, `Rename`, `Từ chối`.

## 3. Kết quả kiểm thử
- `py_compile`: Tất cả các file Python hợp lệ cú pháp.
- `pytest bot/tests`: Toàn bộ 65/65 unit tests đều vượt qua thành công.

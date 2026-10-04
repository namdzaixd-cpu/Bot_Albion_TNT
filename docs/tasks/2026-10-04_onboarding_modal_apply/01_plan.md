# Implementation Plan: Nâng cấp luồng Onboarding nộp đơn qua Multi-step Modal (12 câu hỏi)

## 1. Bối cảnh & Yêu cầu
Thành viên mới gia nhập Discord muốn có quy trình nộp đơn tiện lợi qua nút bấm và Popup Modal thay vì gõ văn bản thủ công dễ sai lệch định dạng. Form yêu cầu đầy đủ 12 trường thông tin:
1. Ingame
2. Năm sinh
3. Giới tính
4. Quốc gia
5. Nguồn biết đến guild
6. Thời gian online
7. Mic giao tiếp
8. Thiết bị (PC/Mobile)
9. Role yêu thích
10. Guild cũ
11. Mục đích vào guild
12. Đồng ý quy định guild

## 2. Giải pháp kỹ thuật
Do Discord giới hạn tối đa 5 `TextInput` components trên 1 Modal, giải pháp tối ưu là triển khai quy trình **Multi-Step Modal (3 bước)**:
- **Bước 1 (5 ô):** Thông tin cá nhân & nguồn gốc.
- **Bước 2 (5 ô):** Thiết bị & kỹ năng chơi.
- **Bước 3 (2 ô):** Mục tiêu & cam kết nội quy.
- **Xử lý hoàn tất:** Gọi SBI Albion API lấy stats, tạo thread trong kênh apply (Forum/Text), hiển thị Embed tổng hợp 12 trường, ping Officer và gắn view duyệt (`OfficerApprovalView`).
- **Lệnh quản trị:** Thêm `/recuibot post_panel` để Officer gửi bảng nộp đơn cố định vào bất kỳ kênh nào.

# Walkthrough: Tối Ưu & Thu Gọn Luồng Apply Onboarding

## 1. Tóm tắt công việc đã thực hiện
Đã giải quyết triệt để tình trạng thread nộp đơn apply bị dài lê thê và lặp lại 3-4 Embed thông tin bằng việc chuyển đổi toàn bộ sang cơ chế **Cập nhật tại chỗ (In-Place Edit)**:

1. **`RulesConfirmView` (Đồng ý nội quy):**
   - Không tạo thêm tin nhắn mới có embed lặp lại.
   - Edit trực tiếp tin nhắn gốc, đổi màu Embed sang Vàng và đổi nút sang `[Đã gửi apply ingame]`.

2. **`ApplicantConfirmView` (Xác nhận gửi đơn in-game):**
   - Loại bỏ nút "Chưa gửi apply ingame" thừa thãi.
   - Edit trực tiếp tin nhắn gốc, cập nhật trạng thái `⏳ Chờ duyệt: <IGN>` và dàn nút Officer `[Accept] [Rename] [Từ chối]`.
   - Gửi 1 dòng text ping ngắn gọn gọi `@Officer` (không kèm Embed).

3. **`OfficerApprovalView` (Duyệt đơn):**
   - Cập nhật trực tiếp Embed thành `✅ Đã duyệt: <IGN>` (màu xanh lá) hoặc `❌ Đã từ chối: <IGN>` (màu đỏ).
   - Tự động cấp Role Member và gửi lời chào mừng thành viên mới.

## 2. Kết quả kiểm tra
- Đã kiểm tra cú pháp: `python -m py_compile bot/cogs/onboarding.py` thành công 100%.
- Giữ nguyên các `custom_id` chuẩn để hỗ trợ Persistent Views khi bot restart.

# Kế hoạch Triển khai: Tối ưu & Thu gọn Luồng Apply Onboarding (In-Place Edit)

## Tổng quan
Tối ưu hóa toàn bộ luồng tiếp đón thành viên mới (Onboarding Apply) trong Cog `bot/cogs/onboarding.py`. Chuyển đổi từ cơ chế gửi tin nhắn liên tiếp kèm Embed lặp lại sang cơ chế **Cập nhật tại chỗ (In-Place Edit)** trên đúng 1 tin nhắn Embed duy nhất, giúp thread apply gọn gàng, liền mạch và chuyên nghiệp.

---

## Chi tiết Thay đổi Logic Luồng Apply

### 1. Bước 1: Khởi tạo đơn Apply (Process Apply Thread)
- **Tin nhắn gốc:**
  - `content`: Nhắc nhở đọc nội quy tại `#rules-channel`.
  - `embed`: Bảng thông số người chơi (Fame, Guild cũ, YOB) màu Xanh dương (`0x3498db`).
  - `view`: `RulesConfirmView` chứa 1 nút `[📘 Tôi đã đọc & Đồng ý Nội Quy]`.

---

### 2. Bước 2: Người mới đồng ý nội quy (`RulesConfirmView`)
- **Hành động:** Sử dụng `interaction.response.edit_message()` để cập nhật trực tiếp tin nhắn bước 1 (KHÔNG gửi tin nhắn mới kèm embed).
- **Cập nhật:**
  - `content`: Nhắc nhở vào game nộp đơn.
  - `view`: Chuyển sang `ApplicantConfirmView` (1 nút xanh lá `[⚔️ Đã gửi apply in-game]`).

---

### 3. Bước 3: Người mới xác nhận đã nộp đơn in-game (`ApplicantConfirmView`)
- **Hành động:** Tiếp tục cập nhật trực tiếp tin nhắn gốc bằng `interaction.response.edit_message()`.
- **Cập nhật:**
  - `embed`: Đổi màu sang Cam (`0xf39c12`), cập nhật tiêu đề: `⏳ Chờ duyệt: {IGN}`.
  - `view`: Chuyển sang `OfficerApprovalView` chứa các nút dành cho Officer: `[✅ Accept]`, `[🏷️ Rename]`, `[❌ Từ chối]`.
  - `channel.send`: Gửi đúng **1 dòng text ngắn gọn** ping Officer (không kèm Embed lặp lại).

---

### 4. Bước 4: Officer duyệt hoặc từ chối (`OfficerApprovalView`)
- **Khi Officer bấm [Accept]:**
  - Chỉnh sửa Embed thành màu Xanh lá (`0x2ecc71`), tiêu đề `✅ Đã duyệt: {IGN}`.
  - Vô hiệu hóa nút Accept/Reject.
  - Cấp Role Member và gửi lời chào mừng.
- **Khi Officer bấm [Từ chối]:**
  - Chỉnh sửa Embed thành màu Đỏ (`0xe74c3c`), tiêu đề `❌ Đã từ chối: {IGN}`.

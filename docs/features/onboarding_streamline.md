# Tính Năng: Tối Ưu & Thu Gọn Luồng Apply Onboarding (In-Place Edit)

## 1. Mục Đích & Vấn Đề Giải Quyết
- **Vấn đề cũ:** Mỗi bước tương tác trong thread nộp đơn (Đọc nội quy -> Gửi đơn in-game -> Chờ Officer duyệt) bot đều gửi tin nhắn mới kèm nguyên bảng Embed to tướng, gây hiện tượng xếp chồng 3-4 Embed giống nhau làm thread bị dài và rối mắt.
- **Giải pháp mới:** Sử dụng cơ chế **Cập nhật tại chỗ (In-Place Edit)** trên duy nhất 1 tin nhắn Embed gốc trong suốt toàn bộ vòng đời đơn apply.

## 2. Luồng Hoạt Động Mới

1. **Khởi tạo đơn Apply:**
   - Bot gửi bảng Embed thông số nhân vật (Fame, Guild cũ, YOB) màu Xanh dương kèm nút `[Tôi đã đọc & Đồng ý Nội Quy]`.

2. **Bước 1 — Người mới bấm đồng ý nội quy:**
   - Bot chỉnh sửa (edit) trực tiếp tin nhắn ban đầu: Chuyển màu Embed sang Vàng (`Gold`), đổi nút sang `[Đã gửi apply ingame]`, nhắc người chơi vào game nộp đơn.

3. **Bước 2 — Người mới bấm đã gửi apply in-game:**
   - Bot chỉnh sửa trực tiếp tin nhắn ban đầu: Đổi Embed sang màu Cam (`Orange`), tiêu đề `⏳ Chờ duyệt: <IGN>`, đổi dàn nút sang dành cho Officer `[Accept] [Rename] [Từ chối]`.
   - Bot gửi duy nhất **1 dòng text ngắn gọn** ping `@Officer` vào duyệt (không gửi kèm Embed duplicate).

4. **Bước 3 — Officer duyệt hoặc từ chối:**
   - Khi bấm `[Accept]`: Embed chuyển sang màu Xanh lá (`✅ Đã duyệt`), khóa nút, cấp role và gửi tin nhắn chúc mừng.
   - Khi bấm `[Từ chối]`: Embed chuyển sang màu Đỏ (`❌ Đã từ chối`), khóa nút.

## 3. Identity, restart và lỗi lưu cấu hình

- Embed gốc giữ URL marker `https://discord.com/channels/<guild_id>/<thread_id>` xuyên suốt các lần đổi tiêu đề/trạng thái. Tin nhắn mới trong đơn đã có report không tạo report hoặc ping Officer trùng.
- Xử lý một thread được khóa riêng; hai ảnh/tin đến đồng thời không tạo hai report.
- Persistent `OfficerApprovalView` được khôi phục theo `message_id` và trạng thái của từng đơn. Không dùng một view chung để disable nút của đơn khác.
- Cấu hình dùng async DB APIs; load lỗi giữ trạng thái chưa sẵn sàng, không dùng kho rỗng để ghi đè. `/recuibot list` báo không đọc được cấu hình thay vì hiển thị mặc định giả.
- Năm sinh: `2000 → 2k`, `2005 → 2k5`, `2010 → 2k10`, `2024 → 2k24`.


# Tính Năng: Hệ Thống Nộp Đơn Multi-Step Modal (12 Câu Hỏi) & Duyệt Đơn Onboarding

## 1. Giới thiệu tổng quan
Tính năng nộp đơn gia nhập Guild TNC được nâng cấp toàn diện từ việc gõ văn bản thuần túy trong thread sang giao diện **Popup Modal đa bước (Multi-step Modal)** trực quan, tiện lợi và chuyên nghiệp trên Discord.

Quy trình giúp thu thập đầy đủ **12 trường thông tin độc lập** mà không bị giới hạn bởi trần 5 ô nhập liệu của Discord API, đồng thời tự động tích hợp tra cứu thông số chỉ số nhân vật (PvE, PvP Fame, Guild) qua SBI Albion API.

---

## 2. Chi tiết 12 Trường Thông Tin Điền Đơn

### 🔹 Bước 1: Thông Tin Cá Nhân & Nguồn Gốc (`ApplyStep1Modal`)
1. **Tên nhân vật Albion (IGN):** Tên chính xác ingame để bot tra cứu SBI API.
2. **Năm sinh:** Năm sinh người chơi (hỗ trợ các định dạng `2000`, `2003`, `2k2`... dùng format nickname sau này).
3. **Giới tính:** Giới tính của thành viên (`Nam` / `Nữ` / `Khác`...).
4. **Quốc gia:** Nơi thành viên đang sinh sống (`Việt Nam`, `Nhật Bản`, `Hàn Quốc`...).
5. **Nguồn biết guild:** Kênh tiếp cận (`Facebook`, `Bạn bè`, `Ingame`, `Discord`...).

### 🔹 Bước 2: Thiết Bị & Kỹ Năng Chơi Game (`ApplyStep2Modal`)
6. **Thời gian chơi game:** Khung giờ online chính (`Tối 19h-23h`, `Cuối tuần`...).
7. **Mic Discord:** Khả năng giao tiếp voice (`Có mic nói chuyện` / `Chỉ nghe được`...).
8. **Thiết bị:** Nền tảng chơi (`PC` / `Mobile` / `Cả 2`...).
9. **Role yêu thích:** Vị trí/vũ khí sở trường (`DPS` / `Heal` / `Tank` / `Support` / `Crafting`...).
10. **Guild cũ:** Tên guild từng tham gia trước đây.

### 🔹 Bước 3: Mục Tiêu & Cam Kết Nội Quy (`ApplyStep3Modal`)
11. **Mục đích vào guild:** Định hướng phát triển (`PvP`, `ZvZ`, `PvE cày fame`, `Giao lưu học hỏi`...).
12. **Đồng ý quy định guild:** Cam kết tuân thủ nội quy chung (`Đồng ý 100%`).

---

## 3. Cơ Chế Hoạt Động Kỹ Thuật

```
[User bấm "📝 Nộp Đơn Gia Nhập Guild"]
               │
               ▼
      [Modal Bước 1/3 (5 ô)]
               │ (Submit)
               ▼
[Bot lưu tạm draft_applications[user_id]]
[Gửi Ephemeral Button: "👉 Điền tiếp Bước 2 / 3"]
               │
               ▼
      [Modal Bước 2/3 (5 ô)]
               │ (Submit)
               ▼
[Bot cập nhật draft_applications[user_id]]
[Gửi Ephemeral Button: "📝 Hoàn tất Bước 3 / 3"]
               │
               ▼
      [Modal Bước 3/3 (2 ô)]
               │ (Submit)
               ▼
[Bot gọi SBI Albion API lấy Fame/Stats/Guild]
               │
               ▼
[Bot tạo Thread trong kênh Apply cấu hình]
               │
               ▼
[Gửi Embed 12 câu hỏi + Stats Albion + ping Officer]
               │
               ▼
[Gắn OfficerApprovalView: Accept | Rename | Từ chối]
```

---

## 4. Danh Sách Lệnh Quản Trị (Officer)

| Lệnh | Phân quyền | Mô tả |
|---|---|---|
| `/recuibot post_panel` | Officer / Admin | Gửi bảng thông báo nộp đơn cố định kèm nút bấm Modal (hỗ trợ tùy biến tiêu đề/mô tả và chọn kênh gửi) |
| `/recuibot set_apply_channel` | Officer / Admin | Cài đặt kênh nộp đơn (hỗ trợ cả `ForumChannel` và `TextChannel`) |
| `/recuibot setup_channels` | Officer / Admin | Cài đặt các kênh Rules, Guild-chat, Q&A |
| `/recuibot setup_roles` | Officer / Admin | Cài đặt Role Officer và Role Member |
| `/recuibot toggle` | Officer / Admin | Bật / Tắt hệ thống tiếp nhận đơn Onboarding |
| `/recuibot list` | Officer / Admin | Xem toàn bộ cấu hình hiện tại và số lượng đơn đang chờ duyệt |

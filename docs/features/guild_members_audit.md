# Tính Năng: Quản Lý Thành Viên In-Game & Đối Soát Nhân Sự Guild (Albion Online)

## 1. Mục Đích & Cơ Chế Hoạt Động
Tính năng hỗ trợ Ban quản trị (Officer) và thành viên Guild TNC tra cứu trực tiếp dữ liệu thành viên in-game thông qua **Albion Online Official Gameinfo REST API** (`gameinfo.albiononline.com`), cung cấp giao diện phân trang trực quan và đối soát nhân sự In-game vs Discord.

## 2. Các Lệnh Hỗ Trợ

### 🔹 `/guildmembers`
- **Mô tả:** Tra cứu danh sách toàn bộ thành viên trong Guild in-game.
- **Tùy chọn:**
  - `sort_by`: Sắp xếp theo `Kill Fame (Cao -> Thấp)`, `Death Fame (Cao -> Thấp)`, `Tên IGN (A -> Z)`.
  - `export_file`: Xuất file `.txt` chứa danh sách đầy đủ toàn bộ thành viên và chỉ số Kill/Death Fame.
- **Giao diện:** View Buttons phân trang (`⏮`, `◀`, `Trang X/Y`, `▶`, `⏭`), hiển thị 12 thành viên/trang.

### 🔹 `/guildaudit` (Officer Only)
- **Mô tả:** Tự động đối soát nhân sự giữa danh sách trong Guild in-game và server Discord.
- **Tính năng lọc Whitelist:** Tự động bỏ qua các IGN đã được thêm vào danh sách whitelist (acc phụ, bot, khách danh dự) khỏi mục cảnh báo *In-game chưa khớp Discord*.
- **Phân loại báo cáo:**
  - 🟢 **Khớp hoàn toàn:** Thành viên có mặt ở cả trong game và trên Discord (khớp Nickname/IGN).
  - 🚩 **In-game chưa khớp Discord:** Thành viên có tên trong Guild in-game nhưng chưa vào Discord hoặc chưa đặt Nickname theo đúng cú pháp IGN.
  - 🛡️ **Đã Whitelist (Bỏ qua):** Liệt kê các IGN nằm trong danh sách bỏ qua đối soát.
- **Đính kèm:** Tự động xuất file text `guild_audit_<guild_name>_<date>.txt` liệt kê chi tiết từng danh sách để Officer tiện quản lý.

### 🔹 `/guildwhitelist` (Officer Only)
- **Mô tả:** Quản lý danh sách các IGN in-game được bỏ qua (whitelist) khi chạy `/guildaudit`.
- **Thao tác:**
  - `action: Xem danh sách whitelist` (`list`): Hiển thị danh sách các IGN đang được whitelist kèm số lượng.
  - `action: Thêm IGN vào whitelist` (`add`), tham số `ign`: Thêm IGN cần bỏ qua (không phân biệt hoa/thường).
  - `action: Xóa IGN khỏi whitelist` (`remove`), tham số `ign`: Xóa IGN khỏi danh sách.

### 🔹 `/registerlist` (Officer Only)
- **Mô tả:** Xem toàn bộ danh sách thành viên Discord đã đăng ký IGN Albion Online (`member_registry`).
- **Giao diện:** Phân trang trực tiếp dạng UI (`RegisterListPaginationView`) với các nút điều hướng `⏮`, `◀`, `Trang X/Y`, `▶`, `⏭` (15 người/trang), hiển thị Discord Tag, ID, Region và IGN đăng ký mà không cần xuất hay tải file.

### 🔹 Cơ Chế Tự Động Register Khi Duyệt Đơn (Onboarding)
- **Mô tả:** Khi Officer bấm **Accept** duyệt đơn xin gia nhập guild tại Onboarding:
  - Bot gọi API kiểm tra trạng thái thực tế của người chơi (`albion_search_player`).
  - Nếu thành viên **thực sự đã ở trong guild in-game**: Bot tự động lưu thông tin vào `member_registry` và thông báo `• [Đã register]` kèm footer embed.
  - Nếu thành viên **chưa ở trong guild in-game**: Bot không tạo register ảo, chỉ gửi thông báo nhắc nhở nộp đơn in-game và hướng dẫn dùng lệnh `/registertnc` sau khi vào guild.

### 🔹 `/guildconfig` (Officer Only)
- **Mô tả:** Cài đặt Guild ID và Khu vực server (`Asia`, `Americas`, `Europe`).

### 🔹 `/guildcheck`
- **Mô tả:** Tra cứu nhanh xem 1 người chơi cụ thể (IGN) hiện có đang ở trong Guild hay không.

## 3. Tính An Toàn & SBI Compliance
- Sử dụng 100% Official Gameinfo REST API công khai.
- Không can thiệp, không đọc bộ nhớ (memory read) hay hook vào client game.
- Hoàn toàn an toàn và tuân thủ chính sách của Sandbox Interactive (SBI).

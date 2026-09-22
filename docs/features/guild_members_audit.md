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
- **Phân loại báo cáo:**
  - 🟢 **Khớp hoàn toàn:** Thành viên có mặt ở cả trong game và trên Discord (khớp Nickname/IGN).
  - 🚩 **In-game chưa khớp Discord:** Thành viên có tên trong Guild in-game nhưng chưa vào Discord hoặc chưa đặt Nickname theo đúng cú pháp IGN.
- **Đính kèm:** Tự động xuất file text `guild_audit_<guild_name>_<date>.txt` liệt kê chi tiết từng danh sách để Officer tiện quản lý.

### 🔹 `/guildconfig` (Officer Only)
- **Mô tả:** Cài đặt Guild ID và Khu vực server (`Asia`, `Americas`, `Europe`).

### 🔹 `/guildcheck`
- **Mô tả:** Tra cứu nhanh xem 1 người chơi cụ thể (IGN) hiện có đang ở trong Guild hay không.

## 3. Tính An Toàn & SBI Compliance
- Sử dụng 100% Official Gameinfo REST API công khai.
- Không can thiệp, không đọc bộ nhớ (memory read) hay hook vào client game.
- Hoàn toàn an toàn và tuân thủ chính sách của Sandbox Interactive (SBI).

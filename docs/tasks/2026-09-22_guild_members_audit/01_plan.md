# Kế hoạch Triển khai: Quản lý & Đối soát Thành viên Guild In-Game (Albion Online)

## Tổng quan
Tích hợp tính năng lấy danh sách thành viên Guild in-game trực tiếp từ **Albion Online Official Gameinfo REST API** (`gameinfo.albiononline.com`), cung cấp giao diện phân trang tra cứu trực quan và tính năng đối soát nhân sự In-game vs Discord cho Ban quản trị Guild (Officer).

---

## Tính năng chính & Luồng hoạt động

### 1. Hàm lấy dữ liệu thành viên từ Official API (`albion_get_guild_members`)
- **Endpoint:** `GET {REGION_API_BASE}/guilds/{guild_id}/members`
- **Region hỗ trợ:** Asia (`gameinfo-sgp`), Americas (`gameinfo`), Europe (`gameinfo-ams`).
- **Dữ liệu trích xuất:**
  - `Name` (IGN), `Id` (Player ID)
  - `KillFame`, `DeathFame`, `FameRatio`
- **An toàn & Hiệu năng:** Sử dụng `aiohttp` bất đồng bộ với timeout 15s, try-except chống lỗi mạng, không block bot event loop.

---

### 2. Lệnh Slash: `/guildmembers`
- **Mô tả:** Tra cứu danh sách thành viên trong Guild in-game.
- **Tham số:**
  - `sort_by` (Lựa chọn): Sắp xếp theo `Kill Fame (Cao -> Thấp)`, `Death Fame (Cao -> Thấp)`, `Tên (A-Z)`.
  - `export_file` (Boolean, mặc định `False`): Tùy chọn gửi kèm file danh sách `.txt` đầy đủ toàn bộ thành viên.
- **Giao diện (Discord UI):**
  - **Embed Phân trang:** Mỗi trang hiển thị 12 thành viên kèm Kill Fame & Death Fame định dạng đẹp (`12.5M`, `350K`).
  - **Nút điều hướng (View Buttons):** `⏮ Đầu`, `◀ Trước`, `Sau ▶`, `Cuối ⏭`, hiển thị `Trang X/Y (Tổng N thành viên)`.

---

### 3. Lệnh Slash: `/guildaudit` (Đối soát In-Game vs Discord - Dành cho Officer)
- **Mô tả:** Đối soát chéo giữa danh sách thành viên trong Guild in-game và danh sách thành viên trên server Discord.
- **Logic đối soát:**
  1. Lấy danh sách toàn bộ IGN trong Guild in-game từ SBI API.
  2. Quét danh sách thành viên Discord (sử dụng `display_name` / `nick` / format `[TAG] IGN`).
  3. Phân loại:
     - 🟢 **Khớp hoàn toàn:** Thành viên có mặt ở cả In-game và Discord.
     - 🚩 **Trong Guild in-game nhưng CHƯA tìm thấy trên Discord:** Thành viên chưa vào Discord hoặc chưa đổi tên theo cú pháp IGN.
- **Kết quả trả về:** Embed tóm tắt số lượng từng nhóm + file báo cáo chi tiết `.txt` đính kèm.

# Tính Năng: Massing CTA & Hướng Dẫn Build Trang Bị (Guild TNC)

## 📌 1. Giới thiệu & Mục tiêu
Tính năng **Massing CTA** là giải pháp nâng cấp chuyên sâu cho hệ thống Massing của Guild TNC, phục vụ các trận đánh Call to Arms (CTA) / ZvZ quy mô lớn:
- Tích hợp sẵn bộ khung đội hình (Comp) CTA 19 vị trí chuẩn (Tank, Support, Healer, DPS).
- Tự động hướng dẫn thành viên build trang bị (Vũ khí, Áo, Mũ, Giày, Off-hand, Cape, Food, Potion) ngay khi nhận slot.
- Tối ưu hóa giao diện Discord bằng Dropdown Select Menu thông minh, vượt qua giới hạn 25 button của Discord khi tạo các party đông người.

---

## ⚔️ 2. Bảng Cấu Hình Đội Hình CTA TNC (19 Slot)

| Vai trò (Role) | Vũ khí (Weapon) | Áo (Armor) | Mũ (Hood) | Giày (Shoes) | Off-Hand | Áo choàng (Cape) | Thức ăn (Food) | Thuốc (Potion) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **🛡️ Tank** | Great Arcane | Knight Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Không dùng) | Smuggle | Avalonian Omelette | Gigan |
| **🛡️ Tank** | Heavy Mace | Guardian Armor | Hellion hood | Royal shoes/Cleric sandals | ❌ (Không dùng) | Smuggle | Avalonian Omelette | Gigan |
| **🛡️ Tank** | Carving | Knight Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Không dùng) | Smuggle | Beef Sandwich | Gigan |
| **🛡️ Tank** | Halbert | Royal Armor | Hellion hood | Royal shoes/Cleric sandals | ❌ (Không dùng) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Locus | Judicator Armor | Assassin hood | Royal shoes | ❌ (Không dùng) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Rootbound | Judicator Armor | Assassin hood | Royal shoes | ❌ (Không dùng) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Lifecurse | Demon | Assassin hood | Guardian Boots | Taproot | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Evensong | Judicator Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Không dùng) | Smuggle | Beef Sandwich | Gigan |
| **💚 Healer** | Hallowfall | Hellion Jacket | Cleric cowl | Royal shoes | Shield | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Fallen | Hellion Jacket | Cleric cowl | Royal shoes | ❌ (Không dùng) | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Blight | Assassin/Hellion jacket | Cleric cowl | Royal shoes | ❌ (Không dùng) | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Rampant | Assassin/Hellion jacket | Cleric cowl | Royal shoes | ❌ (Không dùng) | Smuggle | Avalonian Omelette | Gigan |
| **⚔️ DPS** | Lightcaller | Judicator Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Kingmaker | Soldier Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Galatine | Soldier Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Infinity Blade | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Realm/Greataxe | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Spike Gauntlet/Ursine/Bracer | Hellion jacket/Cultist robe | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Bearpaws | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Không dùng) | Smuggle | Beef Stew | Gigan |

---

## 🛠️ 3. Lệnh và Cách Sử Dụng

### 1. Tạo nhanh party CTA: `/massing_cta [time] [note]`
- **Mô tả:** Lệnh chuyên biệt mở sẵn Form modal với tên `⚔️ CTA ZvZ TNC`, điền sẵn toàn bộ 19 slot CTA và ghi chú hướng dẫn.
- **Tham số:**
  - `time` (tùy chọn): Giờ diễn ra trận đánh (vd: `20:00`, `19:30`).
  - `note` (tùy chọn): Ghi chú riêng của Caller (nếu để trống, bot dùng ghi chú mặc định).

### 2. Sử dụng qua template: `/massing template:CTA TNC`
- Template `CTA TNC (Comp 19 Slot)` được nạp sẵn vào danh sách template của guild, có thể gọi bất kỳ lúc nào từ lệnh `/massing`.

### 3. Tham gia slot và nhận hướng dẫn:
- Thành viên bấm vào Dropdown **"⚔️ Chọn Slot tham gia (Role & Vũ khí)..."** và chọn vị trí mình muốn đánh.
- Bot phản hồi Ephemeral (chỉ thành viên đó thấy):
  - Thông báo đăng ký thành công.
  - Bảng Embed hiển thị đầy đủ chi tiết set trang bị chuẩn của vị trí đó.

### 4. Nút tra cứu nhanh: `🎒 Xem Build`
- Bất kỳ lúc nào thành viên trong party bấm nút này, bot sẽ xác định role/vũ khí thành viên đang giữ và gửi lại bảng hướng dẫn trang bị dạng Ephemeral.

---

## 🔒 4. Hạ Tầng & Bảo Mật Dữ Liệu
- **Khóa đồng thời:** Sử dụng `_massing_state_lock` (asyncio.Lock) bảo vệ toàn vẹn dữ liệu khi nhiều thành viên cùng bấm nhận slot.
- **Lưu trữ:** Tự động đồng bộ JSON state với bảng `json_storage` trên Supabase qua `bot/core/storage.py`.
- **Khôi phục (Restart Persistence):** Toàn bộ View và Button/Select menu của party CTA được khôi phục nguyên vẹn sau khi bot khởi động lại.

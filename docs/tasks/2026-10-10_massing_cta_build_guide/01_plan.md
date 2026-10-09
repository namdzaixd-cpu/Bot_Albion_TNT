# Kế hoạch Triển khai: Hệ thống Massing CTA & Hướng Dẫn Build Trang Bị (Phương án 1)

## 📌 Tổng quan mục tiêu
Nâng cấp và tích hợp vào hệ thống Massing hiện tại (`/massing`) tính năng **Massing CTA ZvZ** với Comp 19 vị trí theo bảng của Guild TNC, kèm cơ chế tự động hiển thị hướng dẫn build trang bị (Weapon, Armor, Hood, Shoes, Off Hand, Cape, Food, Potion) ngay khi thành viên pick role và qua nút bấm tra cứu **"🎒 Xem Build Của Tôi"**.

---

## 📊 1. Dữ liệu Comp CTA & Build Guide Chuẩn TNC

Comp 19 vị trí được cấu hình sẵn gồm:

| Nhóm Role | Vũ khí (Weapon) | Áo (Armor) | Mũ (Hood) | Giày (Shoes) | Off-Hand | Áo choàng (Cape) | Thức ăn (Food) | Thuốc (Potion) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **🛡️ Tank** | Great Arcane | Knight Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Trống) | Smuggle | Avalonian Omelette | Gigan |
| **🛡️ Tank** | Heavy Mace | Guardian Armor | Hellion hood | Royal shoes/Cleric sandals | ❌ (Trống) | Smuggle | Avalonian Omelette | Gigan |
| **🛡️ Tank** | Carving | Knight Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Trống) | Smuggle | Beef Sandwich | Gigan |
| **🛡️ Tank** | Halbert | Royal Armor | Hellion hood | Royal shoes/Cleric sandals | ❌ (Trống) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Locus | Judicator Armor | Assassin hood | Royal shoes | ❌ (Trống) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Rootbound | Judicator Armor | Assassin hood | Royal shoes | ❌ (Trống) | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Lifecurse | Demon | Assassin hood | Guardian Boots | Taproot | Smuggle | Beef Sandwich | Gigan |
| **💜 Support** | Evensong | Judicator Armor | Assassin hood | Royal shoes/Cleric sandals | ❌ (Trống) | Smuggle | Beef Sandwich | Gigan |
| **💚 Healer** | Hallowfall | Hellion Jacket | Cleric cowl | Royal shoes | Shield | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Fallen | Hellion Jacket | Cleric cowl | Royal shoes | ❌ (Trống) | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Blight | Assassin/Hellion jacket | Cleric cowl | Royal shoes | ❌ (Trống) | Smuggle | Avalonian Omelette | Gigan |
| **💚 Healer** | Rampant | Assassin/Hellion jacket | Cleric cowl | Royal shoes | ❌ (Trống) | Smuggle | Avalonian Omelette | Gigan |
| **⚔️ DPS** | Lightcaller | Judicator Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Kingmaker | Soldier Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Galatine | Soldier Armor | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Infinity Blade | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Realm/Greataxe | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Spike Gauntlet/Ursine/Bracer | Hellion jacket/Cultist robe | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |
| **⚔️ DPS** | Bearpaws | Hellion jacket | Cleric cowl | Valor Boots/Stalker shoes | ❌ (Trống) | Smuggle | Beef Stew | Gigan |

---

## ⚙️ 2. Thiết kế Kỹ thuật & Luồng Hoạt động

### A. Tối ưu Giao diện Discord (Xử lý giới hạn 25 component)
* Với 19 vị trí + 10 nút quản lý = 29 component (vượt ngưỡng 25 nút của Discord nếu dùng toàn bộ button riêng lẻ).
* **Giải pháp thông minh:**
  1. Hỗ trợ **Dropdown Select Menu** chọn role/vũ khí nhanh (chia theo role hoặc dropdown tổng hợp danh sách slot trống).
  2. Bố trí action rows khoa học cho party nhiều slot (> 12 slot).
  3. Thêm nút **🎒 Xem Build** trực tiếp trên view party.

### B. Cơ chế Hiển thị Build Guide
1. Khi người chơi pick slot, bot gửi xác nhận kèm Embed hướng dẫn build đồ chuẩn CTA.
2. Nút "🎒 Xem Build" cho phép người chơi xem lại set đồ bất kỳ lúc nào qua Ephemeral embed.

### C. Lệnh Khởi tạo Nhanh: `/massing_cta`
* Lệnh `/massing_cta [time] [note]` mở form modal điền sẵn 19 slot CTA và note hướng dẫn.

---

## 📁 3. Danh sách File Bị Tác Động
1. `bot/cogs/massing.py`
2. `bot/cogs/about.py`
3. `README.md`
4. `docs/features/massing_cta_build_guide.md`
5. `docs/timeline.md`

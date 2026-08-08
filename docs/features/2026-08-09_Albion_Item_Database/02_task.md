# Task — Checklist tích hợp item database Albion

Giai đoạn: **Chỉ nạp data (không phát triển lệnh bot).**

- [x] **1. Chuẩn bị môi trường**
  - [x] Clone `ao-data/albiondata-bin-dumper` → `%USERPROFILE%\albiondata-bin-dumper` (ngoài repo)
  - [x] `dotnet build` — máy có .NET SDK 8.0.422 (build net7.0 OK, chỉ warning)
  - [x] Chuẩn bị: `scripts/albion-item/raw/`, `scripts/albion-item/out/` (gitignored)

- [x] **2. Staging & dump XML**
  - [x] Copy `items.bin`, `spells.bin`, `localization.bin` từ GameData → `raw/`
  - [x] Chạy `DumpAllXML -t Json` → `items.xml`, `spells.xml`, `localization.xml`
  - [x] Xác nhận schema (slottype, enchantments, craftingspelllist, tuv/seg)

- [x] **3. Script trích xuất `scripts/build_albion_item_db.py`**
  - [x] Hàm `load_localizations` — parse 13.745 tags `@ITEMS_`/`@SPELLS_` (EN-US; VI-VN rỗng trong file game)
  - [x] Hàm `load_spells` — 8.903 active/passive spell + tên/mô tả EN
  - [x] Hàm `parse_items` — 1.897 item trang bị (slot: mainhand/offhand/head/armor/shoes/cape/bag), gom stats + enchant `@1..@3` + active/passive
  - [x] `save_json(payload, "tnc_albion_item_v1.json")` lên Supabase `json_storage`

- [x] **4. Chạy & load lên Supabase**
  - [x] Chạy bằng `uv`: `uv run --with supabase --with python-dotenv python scripts/build_albion_item_db.py`
  - [x] `Itemđã lưu 1.897 items (2.20 MB) → tnc_albion_item_v1.json`
  - [x] Verify `load_json` đọc lại: **1.897 items**; sample: `T4_2H_AXE` → "Adept's Greataxe", attackdamage 56, enchant@1 IP 900, spell "Whirlwind"

- [x] **5. Dọn dẹp**
  - [x] Xóa `_items.json` (22.8MB tạm ở root)
  - [x] Xóa `scripts/albion-item/` (raw + out) sau build
  - [x] Thêm `scripts/albion-item/` vào `.gitignore`

- [x] **6. Tài liệu** (`docs/.../2026-08-09_Albion_Item_Database/`)
  - [x] `01_plan.md` — kế hoạch + schema
  - [x] `02_task.md` — checklist (file này)
  - [x] `03_walkthrough.md` — quy trình build lại khi game update

- [ ] **7. Commit & push**
  - [ ] `python -m py_compile scripts/build_albion_item_db.py`
  - [ ] `git add` (docs gitignored → `git add -f`), commit tiếng Việt
  - [ ] `git fetch` + kiểm tra remote trước khi push
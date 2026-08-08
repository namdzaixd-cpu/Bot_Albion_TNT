# Plan — Tích hợp dữ liệu item trang bị Albion (stat/skill/passive) vào Supabase

## Mục tiêu

Tạo script đọc **file game Albion Online** cài local (đã giải mã bằng `albiondata-bin-dumper`) → trích
xuất **item trang bị + stat + skill/passive** → lưu lên Supabase (`json_storage`, 1 blob
`tnc_albion_item_v1.json`). Giai đoạn này **chỉ nạp data — chưa tạo lệnh bot** (không đụng cog,
không sửa `FEATURE_FIELDS` / bảng lệnh README).

## Lý do không dùng albiondatabase.com

Trang `albiondatabase.com` bị **Cloudflare chặn (HTTP 403)** — không scrape được. Các nguồn khác
không đủ:
- `ao-bin-dumps/items.json` (24MB) — chỉ có localization (tên/ID), **không có stat/skill/passive**.
- Albion public API (`gameinfo`) — chỉ player/guild/killboard, không có item stat.

Nguồn duy nhất đủ stat/skill/passive là **file game cài local** (nhị phân vẫn chưa giải mã).

## Nguồn dữ liệu & cơ chế giải mã

Thư mục game:
`C:\Program Files (x86)\AlbionOnline\game\Albion-Online_Data\StreamingAssets\GameData\*.bin` (3.254
file). File `.bin` **được mã hóa DES-CBC + nén GZip**, đầu file có magic bytes `ad ba ca 94`.

- Dùng tool chuẩn: `https://github.com/ao-data/albiondata-bin-dumper` (C#, net7.0).
- `BinaryDecrypter`: Key `[48,239,114,71,66,242,4,50]`, IV `[14,166,220,137,219,237,220,79]`, sau đó
  GZip. CLI: `-m DumpAllXML -d <GameDataFolder> -o <Output> -t Json` → ra XML thật (attribute stat).
- Máy user có .NET SDK 8.0.422 — build net7.0 được (chỉ warning), nếu thiếu runtime n7
  dùng `DOTNET_ROLL_FORWARD=LatestMajor`.

## Các file nguồn được dùng

| File .bin | File XML | Kích thước (raw) | Nội dung |
|---|---|---|---|
| `items.bin` | `items.xml` | ~10MB | item + slottype + stat + enchant + `craftingspelllist` (active skills) |
| `spells.bin` | `spells.xml` | ~8MB | định nghĩa active/passive skill + mô tả |
| `localization.bin` | `localization.xml` | ~72MB | map `@TAG` → tên (EN-US, DE-DE, ...); VI-VN gần như trống cho items |

## Schema dữ liệu

Blob `tnc_albion_item_v1.json` trên Supabase `json_storage` (khóa theo `file_name`):

```json
{
  "meta": {
    "schema_version": 1,
    "source": "GameData items.bin/spells.bin/localization.bin (local machine)",
    "built_at": "2026-08-09T...Z",
    "count_items": 1897
  },
  "items": {
    "T4_2H_AXE": {
      "unique_name": "T4_2H_AXE",
      "name": "Adept's Greataxe",
      "name_vi": "Adept's Greataxe",
      "slottype": "mainhand",
      "tier": 4,
      "stats": { "tier": "4", "slottype": "mainhand", "itempower": "800",
                 "attackdamage": "56", "attackrange": "6", "twohanded": "true", ... },
      "enchant": {
        "T4_2H_AXE@1": { "itempower": "900", "durability": "19059", ... },
        "T4_2H_AXE@2": { ... }
      },
      "spells": {
        "active": [
          { "id": "AXEWHIRLWIND2", "slot": "3", "tag": "A",
            "name_en": "Whirlwind", "name_vi": "", "desc_en": "Spin around ..." }
        ],
        "passive_count": 0
      }
    },
    "...": {}
  }
}
```

- Khóa theo `unique_name` (base, bỏ phần `@N` enchant) → O(1) cho lệnh tra cứu tương lai.
- Enchant variant `@1..@3` nằm trong `enchant` (không ghi khóa base).
- Item **loại bỏ**: food/potion/consumable/resource/reagent/tools/trash — chỉ giữ slottype
  `mainhand, offhand, head, armor, shoes, cape, bag`.

## Các bước thực hiện

1. Clone + build tool ngoài repo (`%USERPROFILE%\albiondata-bin-dumper`, `dotnet build`).
2. Copy `items.bin`, `spells.bin`, `localization.bin` → `scripts/albion-item/raw/`, dump to
   `scripts/albion-item/out/` (gitignored).
3. Viết script `scripts/build_albion_item_db.py` — iterparse XML, lọc item trang bị, gom stats/
   enchant/spells, merge tên EN từ localization, `save_json` lên Supabase.
4. Chạy bằng `uv` (venv có `supabase` + `python-dotenv`).
5. Verify `load_json` đọc lại được dữ liệu. Dọn `scripts/albion-item/` + `_items.json`.
6. Viết docs feature (file này + task + walkthrough).
7. `py_compile` + commit + push (check remote trước).

## Rủi ro / ghi chú

- **XML schema ~thực tế** — đã calibrate tại chỗ (2026-08-09), parse OK 1897 item, skills/chips OK.
- **VI-Viet localization** — file game không có, `name_vi` fallback về `name_en`.
- **Dung lượng** — blob `tnc_albion_item_v1.json` ~2.2MB, dưới giới hạn row `json` nên không cần
  table phụ.
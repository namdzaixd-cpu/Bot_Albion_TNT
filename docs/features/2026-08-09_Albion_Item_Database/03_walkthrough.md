# Walkthrough — Build lại database item Albion khi game update

Tự chạy lại khi game Albion ra bản mới (stat/skill/passive đổi) hoặc cần refresh dữ liệu.

## Tóm tắt

`scripts/build_albion_item_db.py` đọc **file game local** (đã giải mã) → trích xuất item trang bị →
ghi lên Supabase `json_storage` khóa `tnc_albion_item_v1.json`. Data nằm ở Supabase, không phải file
local.

## Bước 0 — Điều kiện

- Có .NET SDK (test: `dotnet --version`). Nếu build/Run lỗi runtime net7: `set DOTNET_ROLL_FORWARD=LatestMajor`.
- Có game Albion cài local tại `C:\Program Files (x86)\AlbionOnline\game\Albion-Online_Data\StreamingAssets\GameData\`.
- Có file `.env` ở repo root chứa `SUPABASE_URL` / `SUPABASE_ANON_KEY` (key đọc/ghi `json_storage`).

## Bước 1 — Clone & build tool (chỉ lần đầu hoặc sau khi tool update)

```powershell
cd $env:USERPROFILE
git clone https://github.com/ao-data/albiondata-bin-dumper.git   # nếu chưa có
cd albiondata-bin-dumper
git pull            # cập nhật khi game đổi format
dotnet build
```

## Bước 2 — Staging & dump XML

```powershell
cd "c:\Users\User\Documents\CODE\NDZ\Bot_Albion_TNC"
New-Item -ItemType Directory -Force scripts\albion-item\raw, scripts\albion-item\out | Out-Null
$gd = "C:\Program Files (x86)\AlbionOnline\game\Albion-Online_Data\StreamingAssets\GameData"
Copy-Item "$gd\items.bin", "$gd\spells.bin", "$gd\localization.bin" scripts\albion-item\raw\

dotnet run --project "$env:USERPROFILE\albiondata-bin-dumper\CommandLine" `
  -m DumpAllXML -d scripts\albion-item\raw -o scripts\albion-item\out -t Json
# → scripts\albion-item\out\{items,spells,localization}.xml
```

## Bước 3 — Chạy script build + load Supabase

```bash
uv run --with supabase --with python-dotenv python scripts/build_albion_item_db.py
```

> `uv` tự tạo venv tạm có `supabase` + `python-dotenv` (máy local không có venv riêng chứa supabase).
> Không dùng `python` thường (hermes venv thiếu supabase thật).

Kỳ vọng log:
```
localizations: 13745 tags (items + spells)
spells: 8903
items: 1897 equipment (skip non-equip 0)
save_json tnc_albion_item_v1.json OK
Đã lưu 1897 items (2.20 MB) → tnc_albion_item_v1.json
Verify load lại: 1897 items từ Supabase.
```

## Bước 4 — Verify dữ liệu trên Supabase

```bash
uv run --with supabase --with python-dotenv python -c "
import sys, os, json
sys.path.insert(0, 'bot'); sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')
from core.storage import load_json
d = load_json('tnc_albion_item_v1.json', {})
print('count:', len((d or {}).get('items', {})))
print(list((d or {}).get('items', {}))[:3])
"
```

Sample kỳ vọng: `T4_2H_AXE` → "Adept's Greataxe", `attackdamage` 56, enchant `T4_2H_AXE@1` itempower
900, active spell đầu "Whirlwind".

## Bước 5 — Dọn dẹp & commit

```bash
rm -rf scripts/albion-item/          # gitignored, không bao giờ commit dump
python -m py_compile scripts/build_albion_item_db.py
git add .gitignore scripts/build_albion_item_db.py
git add -f docs/features/2026-08-09_Albion_Item_Database/
git commit -m "..."    # tiếng Việt theo style repo: tính_năng/sửa_lỗi(...)
git fetch && git push  # kiểm tra remote trước, đừng force
```

## Ghi chú

- **Localization VI**: file game không có dữ liệu tiếng Việt → script `name_vi` fallback `name_en`.
- **Enchant**: biến thể `@1..@3` lưu trong `enchant` với key `tnc_...<base>@N`; key gốc `@0` không
  ghi riêng (lấy từ base).
- **Item bị loại**: food/potion/consumable/resource/reagent/tools/trash — chỉ giữ slot
  `mainhand/offhand/head/armor/shoes/cape/bag`.
- Không chạy bot (`python bot/main.py`) ở local — bản production đang chạy trên Render.
- Thay đổi cách chạy, thay đổi cấu hình — cập nhật task list `02_task.md`.
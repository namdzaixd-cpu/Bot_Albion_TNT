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
# Máy local: dùng Python 3.12 (có supabase). Bỏ "--dry-run" khi thực sự ghi lên Supabase.
"/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe" scripts/build_albion_item_db.py --dry-run
"/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe" scripts/build_albion_item_db.py
```

> `supabase` đang cài ở **Python 3.12** (`User\AppData\Local\Programs\Python\Python312`), không phải
> python mặc định (hermes venv). Kiểm tra: `pip show supabase`.

Kỳ vọng log (schema v2 — item nhánh đã resolve reference, có đầy đủ Q/W/passive):
```
localizations: 13745 tags
spells: 8903
items: 1897 equipment (skip non-equip 0)
MẪU T4_2H_AXE: active=9 passive=4 ref_base=T4_MAIN_AXE | Q: RENDINGSTRIKE, RENDINGSPIN, RENDINGCOMBO
Đã lưu 1897 items (7.55 MB) → tnc_albion_item_v1.json
Verify load lại: 1897 items từ Supabase.
```

## Bước 3b — Dịch skill/passive sang tiếng Việt (Gemini free)

Blob v2 có tên/desc skill **tiếng Anh** (localization En game không có vi). Để chatbot trả lời tiếng Việt
sát nghĩa, dịch bằng Gemini:

```bash
# dry-run đếm pending (không tốn quota)
"/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe" scripts/translate_albion_v1.py --dry-run
# dịch thật → lưu map tnc_albion_translations_v1.json (resume: bỏ qua key đã có)
"/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe" scripts/translate_albion_v1.py
```

> **Key Gemini dạng `AQ` (auth key 2026)**: script gọi qua header `x-goog-api-key` (KHÔNG dùng `?key=`),
> model `gemini-3.5-flash` — các model 2.x-flash hết hạn cho user mới.
> **`.env` có nhiều dòng `GEMINI_API_KEY`**: script ưu tiên dòng ĐẦU TIÊN (key mới nhất do user thêm) —
> đừng sửa/xóa dòng cũ (theo quy tắc bảo vệ .env).
> **Quota free mới**: ~20 req/phút (stricter hơn 1.500/ngày); nếu 429 → script tự chờ `Retry-After`; nếu cạn
> tạm thời, dùng thêm 1 key tài khoản Google khác (append dòng mới phía TRÊN để ưu tiên). Idempotent: chạy lại
> chỉ dịch phần còn thiếu.

## Bước 3c — Merge bản dịch vào blob final

```bash
"/c/Users/User/AppData/Local/Programs/Python/Python312/python.exe" scripts/build_albion_item_db.py --with-translations
```
→ blob v2 giờ có `name_vi`/`desc_vi` trong mỗi skill + `name_vi` item. Nếu skill chưa dịch → fallback `_en`.

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

- **Localization VI**: file game không có dữ liệu tiếng Việt. Dịch bằng Gemini (Bước 3b) → merge (3c).
- **Schema v2**: item nhánh `reference=` đã resolve → thừa hưởng Q/W/passive từ item gốc; `spells.active`
  (slot 1→Q, 2→W, 3→E, tag) + `spells.passive` (PASSIVE_*) + `ref_base` (root gốc).
- **Enchant**: biến thể `@1..@3` lưu trong `enchant` key `<base>@N`; `@0` không ghi riêng.
- **Blob size**: v2 ~7.5MB (full skill). Trigger 1MB `trg_json_storage_size` trong `migration_security.sql`
  chưa apply ở prod (blob hiện đã vượt 1MB vẫn ghi OK) — đừng re-apply nếu không muốn chặn.
- Không chạy bot (`python bot/main.py`) ở local — bản production đang chạy trên Render.
- Thay đổi cách chạy, thay đổi cấu hình — cập nhật task list `02_task.md`.
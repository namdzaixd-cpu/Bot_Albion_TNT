# Verify-Bot

Verify bot sau mỗi lần commit/push/PR — đảm bảo mọi chức năng (từ lệnh đến chatbot,
và **dashboard web** trên Vercel) vẫn hoạt động bình thường, đặc biệt là
**corebank + onboarding**. Chạy nhanh, không cần Discord thật / không chạy bot local.

## Khi nào dùng

- Sau **mỗi commit** hoặc sau khi **push / PR / thay đổi** bất kỳ.
- Khi user nghi ngờ bot production bị lỗi sau thay đổi.

## Quy tắc bắt buộc

1. **KHÔNG** chạy bot thật (`python bot/main.py`) — bot đang chạy 24/7 trên Render;
   chạy thêm ở local gây xung đột Discord gateway + xung đột sync.
2. **KHÔNG** sửa dữ liệu Supabase để "test nhanh".
3. Các bước sau phải chạy **tuần tự** — bước sau dừng nếu bước trước fail.

## Bước 1 — Py-compile (nhanh, bắt syntax)

Chạy từ thư mục gốc repo:

```bash
python -m py_compile bot/core/data/*.py bot/cogs/*.py bot/core/*.py
```

Bất kỳ file nào fail → báo lỗi, sửa trước khi tiếp tục.

## Bước 2 — Pytest toàn bộ

```bash
python -m pytest bot/tests/ -q
```

Cần **tất cả xanh**. Đặc biệt chú ý bộ test "neo" 2 chức năng cốt lõi:

- `bot/tests/test_corebank_logic.py` — corebank: parse emoji, thứ tự react, luồng
  `on_message` (react/tách ảnh/bỏ qua), slash command, config an-toàn-dưới-lỗi.
- `bot/tests/test_onboarding_logic.py` — onboarding: `_format_yob`, `validate_form`,
  regex biểu mẫu, `get_onboard_data`, group `recuibot`, config an-toàn-dưới-lỗi.

Nếu 2 bộ này fail → **dừng**, không commit/push. Báo rõ test nào fail.

## Bước 3 — Kiểm tra biến môi trường + Supabase (health, optional)

Kiểm tra `.env` local có đủ biến tối thiểu (đừng in giá trị secret):

```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); \
print('SUPABASE_URL', bool(os.getenv('SUPABASE_URL'))); \
print('SUPABASE_ANON_KEY', bool(os.getenv('SUPABASE_ANON_KEY'))); \
print('DISCORD_TOKEN', bool(os.getenv('DISCORD_TOKEN')))"
```

Nếu Supabase OK, có thể test đọc 1 key dữ liệu thật:

```bash
python -c "import os,sys; sys.path.insert(0,'bot'); from core.storage import load_json; \
d=load_json('tnc_albion_item_v1.json',{}); print('items:', len(d.get('items',{})) if isinstance(d,dict) else 0)"
```

## Bước 4 — Dashboard build offline (web_dashboard/)

Dashboard là Next.js (Next 16, NextAuth, Supabase). Build offline để bắt lỗi
type/route/import mà KHÔNG cần OAuth/Discord thật (env trong code đều fallback
`""` nên build không vỡ khi thiếu biến).

```bash
cd web_dashboard && npm run build
```

- Thành công → thấy danh sách route gồm `✓ Generating static pages`,
  `ƒ /api/auth/[...nextauth]`, `ƒ /api/corebank`, `○ /dashboard`, `ƒ Proxy (Middleware)`.
- **Lưu ý:** build tạo thư mục `web_dashboard/.next` — sau khi build xong phải
  `rm -rf .next` (thư mục này không track trong git). Kiểm tra lại
  `git status --short -- web_dashboard` sạch.
- Nếu fail (lỗi type, route, import) → báo lỗi, sửa trước khi commit/push.

## Bước 5 — Báo cáo + quyết định commit

- Kết quả phải báo rõ ràng: **✅/❌** từng nhóm (py_compile, pytest, env, storage,
  dashboard build).
- Nếu mọi thứ pass → mới commit/push theo quy trình chuẩn (Vietnamese message,
  không `Co-Authored-By`, `git fetch` trước, kiểm tra xung đột).
- Nếu có alert ≥ 2 → nhắc user kiểm tra Render/`.env` (production).

## Checklist dùng cho mỗi thay đổi

- [ ] `py_compile` tất cả file Python trong `bot/`
- [ ] `pytest bot/tests/` → 100% xanh (nhất là corebank + onboarding)
- [ ] Env tối thiểu tồn tại (`SUPABASE_*`, `DISCORD_TOKEN`)
- [ ] (Nếu đổi schema) đọc thử 1 key dữ liệu qua `core.storage.load_json`
- [ ] Dashboard: `npm run build` (trong `web_dashboard/`) xanh, `.next` đã dọn
- [ ] Không có bot local đang chạy
- [ ] `git fetch` → không xung đột → commit tiếng Việt → push

## Lưu ý về 2 chức năng neo (corebank + onboarding)

Đây là những gì test bảo vệ — **đừng** bỏ/refactor các test này khi không đụng
logic liên quan; nếu refactor logic thật, cập nhật test song song. Khi thêm lệnh
mới cho 2 hệ này, nhớ cập nhật cả `test_*_slash_commands_registered` + README +
`FEATURE_FIELDS` trong `bot/cogs/about.py`.

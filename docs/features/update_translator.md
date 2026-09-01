# Tính năng: Tự động tạo Thread + Dịch kênh #update (Update Translator)

> **Ngày**: 2026-09-01
> **Cog**: `bot/cogs/update_translator.py`
> **Trạng thái**: Mới

---

## Mục đích

Kênh `#update` trong guild chứa các thông báo cập nhật (chủ yếu tiếng Anh). Bot tự động:

1. Tạo **1 thread** gắn vào mỗi tin cập nhật mới trong kênh.
2. AI (Gemini) đặt **tiêu đề thread** theo nội dung bản cập nhật.
3. Gemini **dịch nội dung sang tiếng Việt** và post vào thread.
4. Cho phép user **yêu cầu dịch lại** khi gặp tin cũ.

Chỉ dịch **message bài chính** — không dịch các replies trong thread.

## Cơ chế hoạt động

### Luồng tự động (tin mới)

```
Tin mới trong #update
  ├─ Bot đặt tiêu đề (Gemini: "Đặt tiêu đề ngắn cho bản cập nhật...")
  ├─ Bot tạo thread → message.create_thread(name=title, auto_archive_duration=1440)
  ├─ Bot dịch nội dung sang tiếng Việt (Gemini)
  ├─ Post "<🇻🇳> **Bản dịch tiếng Việt:**" + nội dung dịch (split nếu > 2000 ký tự)
  └─ Lưu mapping message_id → thread_id vào config
```

### Luồng yêu cầu dịch lại

- **React 🇻🇳** lên 1 tin trong #update → bot đảm bảo thread + bản dịch tồn tại
  (nếu tin là media-only vẫn tạo thread ghi chú, không có bản dịch).
- **Tag bot** (vd `@Bot dịch tin này`):
  - Nếu reply vào tin nào → dịch đúng tin đó.
  - Nếu không reply → tìm tin không-phải-bot gần nhất phía trên.
  - Post bản dịch reply vào chính tin tag (không đổi thread).

## Điều kiện lọc message

- Không phải bot.
- Có guild (không áp dụng DM).
- Thuộc `discord.TextChannel` **đang trong danh sách config** (`channel_ids`).
- Không phải lệnh prefix (`!`, `.`).
- Không phải message trong thread (thread giữ lại bản dịch).

## Lưu trữ (Supabase json_storage)

Key config: **`tnc_updatetranslator_v1.json`** (qua `load_json()`/`save_json()`).

```json
{
  "enabled": true,
  "channel_ids": [111111111111111111],
  "threads": {
    "1200000000000000000": "1300000000000000000"
  }
}
```

| Field | Kiểu | Ý nghĩa |
|---|---|---|
| `enabled` | bool | Bật/tắt toàn tính năng |
| `channel_ids` | list[int] | ID các kênh cần tự dịch (thêm qua `/utconfig`) |
| `threads` | dict[str→int] | Mapping `message_id` → `thread_id` (tránh tạo thread/đăng trùng) |

## Gemini

- Gọi REST: `generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`.
- Dùng **`GEMINI_API_KEY`** từ `.env` (đã có sẵn, không cần thêm key).
- Không dùng thư viện Gemini — dùng `aiohttp` (đã là dependency) để không thêm package.
- Mọi lỗi / thiếu key đều bọc `try-except` → **không bao giờ crash bot (CI-safe)**.
- Nếu thiếu key: vẫn tạo thread (title fallback = dòng đầu tin), bỏ qua dịch, log cảnh báo.

## Slash commands

| Command | Perm | Mô tả |
|---|---|---|
| `/utconfig channel:<tên>` | Officer | Thêm kênh #update vào danh sách tự dịch |
| `/utconfig enable:on|off` | Officer | Bật/tắt tính năng |
| `/utstatus` | mọi user | Xem cấu hình (kênh, trạng thái, số thread, key Gemini) |

Giao diện `/utstatus`:
```
🔛 Trạng thái: BẬT
📌 Kênh: #update
🤖 Gemini API key: ✅ Có
🧵 Số thread đã tạo: 5
```

## Edge cases

- **Tin media-only (không có text)**: vẫn tạo thread? — Không. Bot chỉ tạo thread + đặt title bằng AI
  khi có nội dung text. Tin media-only được react/bản dịch tự động skip (không có text để dịch).
  → Cập nhật: Bot vẫn tạo thread cho tin media-only với ghi chú `[Không có nội dung text...]` nếu
  được react 🇻🇳 yêu cầu; còn tin tự động mới thì bỏ qua hoàn toàn tin không có text.
- **Nội dung > 2000 ký tự**: cắt theo dòng, post nhiều message, đánh số thứ tự tự nhiên.
- **Trùng lặp**: kiểm tra `threads[message_id]` trước khi tạo thread → idempotent.
- **Chạy trùng (gateway lặp)**: `self.in_progress` set chống xử lý đồng thời cùng 1 message.

## Tuân thủ dự án

- Lưu trữ qua `load_json`/`save_json` — không `open()` thuần.
- Không đụng `.env` (dùng key có sẵn).
- Không thêm dependency mới.
- Mọi kết nối ngoài bọc try-except (quy tắc CI).
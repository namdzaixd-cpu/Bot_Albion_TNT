# Storage keys và dữ liệu legacy

Dữ liệu JSON vận hành hiện nằm trên **Supabase `json_storage`**, khóa `file_name = basename(path)`. `bot/Storage/` là thư mục legacy, không phải nơi bot ghi state thật và không còn tự GitHub sync/backup `.bak`.

## Quy tắc bảo vệ

- Không sửa/xóa các snapshot legacy có sẵn để test; không đặt test, log hoặc file tạm tại thư mục này.
- Dữ liệu JSON vận hành phải đọc/ghi qua `bot/core/storage.py`, không `open()` thuần hoặc gọi trực tiếp Supabase để bypass storage contract.
- Runtime async dùng `load_json_async(path, default)` / `save_json_async(data, path)`. Sync `load_json` / `save_json` chỉ dùng trong script sync thực ngoài event loop.
- Default chỉ khi row không tồn tại. Request lỗi phải được xử lý như lỗi; không dùng empty default làm snapshot authoritative rồi ghi đè kho.
- Persist thất bại raise lỗi; không báo đã lưu. Async write copy payload trước offload để các edits concurrent không đổi dữ liệu đang ghi.
- Snapshot legacy import cần nguồn offline explicit và chạy có chủ đích; không tự import thư mục này lúc startup/test hoặc overwrite DB từ snapshot cũ.

## Khóa JSON runtime

| Khóa | Cog/consumer |
|---|---|
| `tnc_massing_v1.json` | Active parties và restore views Massing. |
| `tnc_templates_v1.json` | Templates Massing. |
| `tnc_guildcheck_v1.json` | Cấu hình GuildCheck. |
| `tnc_bot_status.json` | Heartbeat main bot. |

Các key khác theo constant trong cog sở hữu; tên mới theo `tnc_<tính_năng>_v<version>.json`. Đường dẫn `STORAGE_DIR` chỉ tạo basename key, không tạo file runtime local. Không thêm vào `GITHUB_SYNCED_FILES` vì cơ chế đó đã bỏ.

SP, CoreBank ledger/config, LastSeen, TTS config và danh mục Discord dùng các bảng chuyên biệt qua lớp DB; không cập nhật snapshot JSON legacy để thay dữ liệu bảng.

Xem `DATABASE_ARCHITECTURE.md` cho schema, transaction, error semantics, test isolation và rollout.

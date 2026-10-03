# Kiến trúc dữ liệu Bot TNC

## Backend và quyền truy cập

Bot Python và Next.js API server dùng Supabase server-side. Browser gọi API dashboard đã xác thực; không nhận service-role key, bank token hoặc webhook secret. Thao tác ghi dashboard cần Discord user ID trong `ADMIN_DISCORD_IDS` ở cả proxy và route handler.

`SUPABASE_SERVICE_ROLE_KEY` là key backend được ưu tiên. Anon key không thay thế quyền backend: RLS/privileges không cho anon hoặc authenticated truy cập trực tiếp bảng vận hành. Thiếu cấu hình DB là lỗi rõ ràng, không phải kho dữ liệu rỗng.

## Python APIs

| Module | Contract |
|---|---|
| `bot/core/db.py` | `async_execute(builder)` chạy Supabase sync I/O ngoài event loop, trả `(response, error)`. Builder trả query chưa execute. Mutation mặc định một attempt; không retry khi kết quả chưa rõ. SELECT có retry/backoff; PostgREST client timeout 10 giây mỗi request. |
| `bot/core/storage.py` | `load_json_async(path, default)` và `save_json_async(data, path)` cho runtime. Basename là `json_storage.file_name`; không đọc/ghi file JSON local. Default chỉ khi row không có; lỗi DB raise `DBError`. Save snapshot payload trước offload và raise nếu persist thất bại. |
| `bot/core/config_store.py` | Async get/save; cached row được copy. Read lỗi không cache default; generation chặn in-flight read cũ phục hồi cache sau invalidate. Save invalidate cache sau persist, không mutate row authoritative trước commit. |
| Sync APIs cùng module | Dành cho script thực ngoài event loop. Không gọi trong constructor/lifecycle/listener/command async của bot. |

Không còn `core.database` forwarding shim hoặc GitHub JSON-sync startup stub. Không đọc dữ liệu vận hành bằng `open()` hoặc gọi thẳng Supabase ngoài lớp dữ liệu tương ứng. `bot/Storage/` là legacy; không đặt test/log/file tạm vào đó.

## Các bảng

| Bảng | Vai trò |
|---|---|
| `guild_config` | Guild identity, onboarding channels/roles/toggle. |
| `corebank_config` | Cấu hình CoreBank theo `DISCORD_GUILD_ID`; token chỉ backend. |
| `core_credited` | Durable payment ledger: Officer, recipient/amount/emoji snapshot và trạng thái thanh toán/hoàn tác. |
| `user_economy`, `sp_metadata`, `sp_transactions` | Tổng điểm, watermark và lịch sử SP; commit atomic trong RPC. |
| `user_activity` | LastSeen; flush lỗi giữ dirty để retry. |
| `alo_tts_config` | Cấu hình TTS. Queue runtime được gắn channel/session nguồn. |
| `json_storage` | Party/template, GuildCheck, translator mapping và heartbeat theo file-name key. |
| `discord_channels`, `discord_roles` | Danh mục Discord được Sync cập nhật. |
| `system_logs` | Log bot; Overview/API logs đọc bảng này, không đọc bảng `logs` cũ. |
| `blacklist` | `source_guild_id` tham chiếu guild; actor lấy từ session server-side. |
| `ai_config`, `chat_history` | Contract lịch sử còn dùng bởi dashboard/helper; chatbot chạy repo riêng. Không tự chuyển dữ liệu giữa hai project. |

Không tạo `logs` hoặc `siphoned_energy` rỗng để làm query cũ hết lỗi: consumers dùng bảng producer thật.

## Core payments và kết quả chưa rõ

Claim theo credit key unique và transition conditional atomic trong DB. Validate token/recipient trước claim; claim lỗi/duplicate không gửi thanh toán. Refund dùng amount/recipient snapshot, không dùng giá emoji hiện tại.

UnbelievaBoat PATCH là phép đổi balance bên ngoài transaction PostgreSQL. Không có bằng chứng contract idempotency key hoặc transaction-history endpoint trong API đã kiểm tra. Timeout, lỗi không xác định hoặc crash sau gửi có thể xảy ra sau khi balance đã đổi: không tự retry rồi cộng/trừ lần hai.

Ledger giữ `pending`/`unknown` hoặc `reverting`/`refund_unknown` khi chưa xác minh; record cũ không mặc định đã trả tiền. `scripts/corebank_reconcile.py` yêu cầu credit key, quyết định, actor và bằng chứng; legacy cần bổ sung guild, recipient, emoji key, tên và display snapshot. DB lưu actor/evidence/timestamp. Helper chỉ ghi kết quả đã kiểm chứng, không gọi bank API và không suy ra kết quả từ balance hiện tại.

## SP transaction và autosave

SP import parse các dòng hợp lệ, không phụ thuộc thứ tự file. RPC lock watermark, cộng delta, ghi history và tiến watermark trong cùng transaction; failure rollback toàn bộ. Các lệnh chỉnh/reset điểm dùng cùng lock, không upsert whole snapshot cũ đè import concurrent.

Dashboard PATCH chỉ gửi field thay đổi. Core emoji map dùng atomic per-key mutation; thay hai key khác nhau không mất nhau. Token không có trong PATCH nghĩa là giữ token đang lưu. UI serialize edits cùng page; persist thành công nhưng reload lỗi vẫn giữ trạng thái DB đã lưu và hiển thị chưa áp dụng.

## Reload và health

- Bot/dashboard dùng cùng `DISCORD_GUILD_ID`, fallback `712258265769050164`; không dùng một biến `GUILD_ID` dashboard riêng.
- Legacy CoreBank `default` được chuyển sang guild thật chỉ khi row guild thật chưa có; không overwrite row hiện có.
- Server webhook dùng `Authorization: Bearer <WEBHOOK_SECRET>`; secret giống nhau trên deployments liên quan. Thiếu cấu hình fail-closed; thiếu/sai header không dispatch.
- Persist thành công nhưng webhook lỗi được báo là đã lưu/chưa áp dụng, không báo đã áp dụng giả.
- `applied: true` nghĩa là cả hai webhook đã nhận yêu cầu reload thành công, không phải ACK rằng mọi async listener đã đọc DB xong. Cần log/health của deployments để xác nhận áp dụng thực; listener gặp DB lỗi giữ cấu hình cũ.
- Heartbeat online lấy gateway readiness hiện tại. `/api/bot-status` trả `{main_bot, chatbot}`; timestamp quá 90 giây là stale. Web service trả HTTP không đồng nghĩa bot kết nối Discord.

## Bootstrap và migration

Luồng hiện hành: `scripts/schema.sql` → sorted `scripts/migrations/*.sql` → `scripts/migration_security.sql`, trên một connection/transaction bằng `scripts/apply_schema.py`.

```bash
# Chỉ dùng connection của DB đã chọn có chủ đích. Không chạy để test production.
python scripts/apply_schema.py
```

Runner lấy `DIRECT_URL` hoặc `DATABASE_URL` từ environment, không đọc dotenv khi import, không split SQL bằng dấu `;`, không log connection string có password. Dependency: `psycopg[binary]` trong requirements. Thay đổi schema qua cơ chế SQL đã version hóa; `node scripts/db-exec.js "SQL_DDL"` vẫn là tiện ích DDL theo quy tắc repo khi chạy trên DB được cấp quyền.

`scripts/migration.sql` là snapshot lịch sử chứa UPSERT số dư/watermark/config; **không áp file này để bootstrap/upgrade DB đang hoạt động**. `schema_v2.sql` là migration lịch sử, không nằm trong runner hiện hành. Không reset/truncate hoặc seed snapshot vận hành để migration xanh.

Bootstrap tạo đủ bảng trước FK/index/RLS/RPC. Upgrade additive giữ dữ liệu legacy; FK `NOT VALID` giữ orphan cũ mà vẫn kiểm tra writes mới. Cần đối soát orphan có chủ đích trước validate, không map nhãn nguồn thành guild ID giả. RLS và table privileges chỉ cho backend service role; RPC state-changing chỉ service-role execute.

## Verification và rollout

Tests Python chặn dotenv/outbound network trước import, không dùng credential máy thật. SQL được exercise trên PostgreSQL disposable UTF-8 bằng synthetic fixtures: empty bootstrap, legacy upgrade, reapply, rollback/concurrent operations và permissions. Không chạy Discord bot thật local.

Rollout cần: backup hợp lệ → apply DDL additive đã verify → cấu hình `WEBHOOK_SECRET` giống nhau hai phía → deploy bot/dashboard tương ứng → kiểm tra production health/đường đã đổi. Không coi sửa source là đã deploy hoặc đã thu hồi credential.

Credential từng hard-code trong `scripts/create_tables.py` phải rotate qua quyền quản trị provider nếu còn hiệu lực. Không in credential, không sửa lịch sử Git tự động, không overwrite dòng `.env`; thay đổi local env chỉ append và đồng bộ env example.

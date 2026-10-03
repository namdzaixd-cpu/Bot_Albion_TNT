# Toàn vẹn dữ liệu và runtime — F01–F36

## CoreBank: claim, trả tiền và đối soát

`core_credited.message_id` giữ credit key `<message_id>:<emoji_key>`. Claim lưu guild, Officer, recipient, amount, emoji/name/display snapshot và trạng thái trước khi gọi provider. Claim trùng hoặc lỗi không gửi tiền.

| Trạng thái | Ý nghĩa/đường đi |
|---|---|
| `legacy_unknown` | Record cũ chưa chứng minh đã trả tiền; không auto-refund. |
| `pending` | Claim đã có; kết quả provider chưa xác nhận. |
| `unknown` | HTTP lỗi/timeout hoặc kết quả chưa rõ; không gửi lại tự động. |
| `credited` | Provider trả thành công và DB đã ghi nhận. |
| `reverting` | Một caller đã nhận quyền hoàn tiền. |
| `refund_unknown` | Hoàn tiền chưa rõ kết quả; không trừ lại tự động. |
| `reverted` | Hoàn tiền đã được xác nhận và ghi DB. |
| `retryable` | Operator xác nhận chưa trả tiền bằng chứng bên ngoài; claim mới phải khớp snapshot cũ. |

Refund dùng recipient/amount/name/display đã lưu, kể cả emoji đã đổi giá hoặc bị xóa. Repost attachment lỗi giữ tin gốc. Config load đầu kỳ lỗi để module ở trạng thái chưa sẵn sàng, không làm sập toàn bộ setup và không hiển thị empty config như dữ liệu thật; reload thành công khôi phục module.

Provider PATCH nằm ngoài transaction DB. Unique claim **không chứng minh exactly-once của provider** khi mất ACK. Tài liệu đã tham khảo không mô tả idempotency key hoặc endpoint tra cứu transaction history:

- [UnbelievaBoat — Update User Balance](https://api-docs.unbelievaboat.com/reference/patch-user-balance)
- [UnbelievaBoat — Authentication](https://api-docs.unbelievaboat.com/reference/authentication-1)

Operator dùng `python scripts/corebank_reconcile.py --help`. Các quyết định `paid`, `not_paid`, `refund_applied`, `refund_not_applied` phải phù hợp trạng thái hiện tại; actor/evidence bắt buộc và được lưu cùng timestamp. Legacy cần guild, recipient, emoji key, core name/display và amount cũ phải hợp lệ. Helper không gọi provider, không suy ra payment bằng balance hiện tại và không sửa record dựa trên phỏng đoán.

## SP: một transaction cho import và chỉnh điểm

Parser bỏ dòng timestamp/amount không hợp lệ. `apply_siphoned_import` khóa row watermark; balance delta, history và max timestamp hợp lệ cùng commit hoặc cùng rollback. File tăng/giảm thứ tự cho cùng kết quả; reupload phần đã nhập không cộng lại. Dòng lỗi có timestamp mới hơn không đẩy watermark.

`adjust_siphoned_points`, `delete_siphoned_users`, `reset_siphoned_points` dùng cùng lock với import. Không đọc toàn bộ bảng rồi ghi lại snapshot điểm cũ. History và bảng điểm là hai dữ liệu khác nhau: metric `siphoned_count` đếm `user_economy`, không đếm transaction.

## Massing, LastSeen, TTS

- Massing load party/template trước khi phục hồi view. SELECT lỗi giữ state đã có và khóa ghi; không persist kho rỗng. Cleanup đầu kỳ chờ đủ bảy ngày, kể cả startup không có party.
- Mutations Massing/template được khóa xuyên suốt snapshot → mutate → persist → rollback. Callback ACK trước khi đợi lock. Save lỗi của party A không xóa cập nhật đang chờ của party B.
- Slot đích đầy được kiểm tra trước khi bỏ slot/fill cũ. Form kiểm tra giới hạn 25 component, custom ID và label ở **mức đầy tối đa**, trước khi publish state.
- LastSeen chỉ clear dirty sau mọi chunk thành công và revision không đổi. Failed flush vẫn retry được dù không có message mới; shutdown save không giả success.
- Queue TTS giữ source channel ID. Move A→B cập nhật session, dừng audio hiện tại và bỏ backlog A; worker kiểm tra lại channel/session ngay trước playback. Config read-name/rejoin và GuildCheck ID/region được khóa read-modify-write để giữ các chỉnh sửa đồng thời.

Onboarding và translator có cơ chế identity/khôi phục riêng: xem [onboarding_streamline.md](onboarding_streamline.md) và [update_translator.md](update_translator.md).

## Dashboard và reload

- Bot/dashboard dùng cùng `DISCORD_GUILD_ID`. Legacy `default` chỉ copy vào canonical guild row còn thiếu; không overwrite row thật hoặc xóa nguồn.
- CoreBank GET/PATCH không trả raw token; `token_configured` là boolean. Omit token khi PATCH giữ nguyên giá trị. Scalar patches và emoji-key mutations không overwrite edit độc lập.
- UI serialize autosave. Module update đã lưu nhưng reload lỗi giữ đúng trạng thái persisted, hiển thị lỗi và refresh overview; API/status lỗi hiển thị chưa xác định, không giả offline/đã tắt/empty success.
- Webhook yêu cầu `Authorization: Bearer <WEBHOOK_SECRET>`; secret chỉ server-side. `applied: true` là cả hai HTTP webhook đã nhận reload, **không phải** ACK rằng async listeners đã hoàn thành.
- Heartbeat online là gateway readiness ở từng tick, không phải trạng thái web server.

## Migrations, helpers và triển khai

Runner hiện hành: `scripts/schema.sql` → versioned migrations → `scripts/migration_security.sql`, một transaction. Không dùng operational snapshot `scripts/migration.sql` để bootstrap/upgrade. FK `NOT VALID` giữ orphan legacy, vẫn kiểm tra writes mới; cần đối soát trước validate.

Helpers JSON chỉ đọc export offline được chọn rõ bằng `--legacy-snapshot-dir`; từ chối `bot/Storage`, thư mục bao chứa hoặc symlink thoát source. Missing source thất bại trước DB write. Diagnostics offline mặc định; live read phải chọn `--check-live`. AI helper yêu cầu `--instruction-path`/`AI_INSTRUCTION_PATH` thật trước menu/provider.

Rollout yêu cầu backup, apply DDL được kiểm chứng, guild row hợp lệ, secret đồng nhất, deploy các ứng dụng liên quan và xác nhận log/health. Chatbot là repo/deployment riêng; phải xác nhận receiver hỗ trợ contract reload trước rollout. Credential DB từng có trong source cần rotate bằng quyền provider, kể cả đã xóa source: Git history không tự thu hồi mật khẩu.

Đợt này kiểm chứng offline/disposable, không đổi DB hoặc `.env` production, không khởi động bot thật, không tự push/deploy. Evidence: [walkthrough](../tasks/2026-10-04_full_project_fixes/03_walkthrough.md).

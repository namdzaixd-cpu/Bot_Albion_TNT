# Walkthrough — sửa F01–F36

## Kết quả và giới hạn

Phần mã nguồn của đủ F01–F36 đã sửa và exercise trên môi trường cô lập. Không có bằng chứng production rollout hoặc credential cũ đã rotate; mục tiêu vận hành vẫn mở. Ma trận từng finding: [02_task.md](02_task.md). Cơ chế hiện hành: [data_integrity_and_runtime.md](../../features/data_integrity_and_runtime.md).

Không chạy `bot.run`, Discord login/gateway, bank provider thật hoặc migration trên DB production. Không sửa `.env` và không push/deploy. Browser chạy Next.js/Flask thật, session/API synthetic tại boundary; PostgreSQL là cluster disposable local. Đây không phải production end-to-end verification.

## 1. Python và TypeScript

- Compile **41 Python files** thuộc đợt sửa bằng `python -m py_compile`, bytecode cache ở temp; kết quả exit 0. Compile thêm lượt cuối cho `corebank.py` và `test_financial_invariants.py` sau patch unavailable/recovery: exit 0.
- `python -m pytest -q`: **61 passed in 1.28s**, exit 0. Conftest chặn dotenv và outbound socket trước imports. Không còn test khóa source text, wording, command count hoặc default-only constructor behavior.
- `npm run build` với source cuối, dependencies local và environment synthetic: Next.js **16.2.12** compile thành công, TypeScript phase thành công, generate **21/21** pages; exit 0. Không copy `.env` vào verification build.

## 2. PostgreSQL thật, integrations ngoài giả tại boundary

Đã áp `schema.sql`, baseline/dashboard/financial/metrics migrations và security hardening trong một transaction:

- **Empty DB/reapply:** tạo đủ tables/RPC và áp lại thành công, không UPSERT operational snapshot.
- **Legacy upgrade:** balances, watermark, party JSON và orphan rows được giữ. Core ledger lịch sử chuyển thành unknown/legacy state; row canonical có sẵn không bị row `default` overwrite.
- **Atomic apply:** schema chứa function/DO block và semicolon chạy nguyên SQL. Inject failure ở file cuối: không còn partial tables sau rollback; schema CLI thật exit 0 khi success, thiếu DB URL fail rõ trước connect.
- **Core claim/refund:** nhiều caller chỉ một claim và một refund owner. Cog tài chính thật gọi RPC/cache/DB thật với provider fake: payout 100, đổi giá/xóa emoji rồi refund vẫn 100; provider HTTP504 giữ unknown, không resend. Blank reconciliation evidence bị từ chối trước khi thay unknown state.
- **SP:** concurrent imports cộng đúng một lần; manual delta không mất dưới import. Fixture import 350 + manual 3 cho balance **353**. Invalid amount/timestamp không đẩy watermark; reupload applied 0. Failure sau balance/history write rollback cả balance, history và watermark.
- **Config:** scalar/per-emoji concurrent edits giữ cả keys độc lập và token chưa gửi; legacy migration không overwrite. Guild-scoped metric fixture trả corebank_total **70**, siphoned_count **3**, blacklist_count **1**, ai_today **0** theo module `ai` thực.
- **Permissions:** RPC financial/metric không execute được bằng anon/authenticated; service_role có quyền. FK hợp lệ cho blacklist server-sourced guild.

Không suy ra exactly-once của bank provider từ unique DB claim. Outcome chưa rõ vẫn cần operator evidence; helper reconciliation không gửi request thanh toán.

## 3. Runtime Discord functions/handlers thật

Throwaway scripts gọi functions/cogs thật, fake interaction/channel/provider ở boundary, không login bot:

- Cold setup đăng ký cogs/commands; watchdog khởi tạo None, repeated ready không tạo task trùng, disconnect đủ 180s mới gọi SIGTERM fake.
- DB unavailable cold setup: CoreBank ở trạng thái chưa sẵn sàng, `/corelist` trả lỗi unavailable chứ không empty config embed; các cogs khác vẫn được load. Regression kiểm chứng reload thành công khôi phục cùng cog.
- Restore hai party Massing tạo view trước cleanup, không clear tức thì. Empty startup vẫn có cleanup sau đủ tuần. Failed party/template load giữ state cũ và khóa overwrite.
- Một join save đang block rồi lỗi, join party khác chờ lock: ACK trước, rollback không xóa edit độc lập và save sau chứa đúng edit đó.
- Move vào slot đầy giữ slot/fills cũ và DB state; tạo vacancy rồi move đúng một lần. Form 26 components hoặc label 81 ký tự tại capacity bị từ chối trước tạo orphan party.
- Failed LastSeen flush giữ dirty; retry thành công khi không có message mới.
- TTS move A→B bỏ backlog A trước generate/playback. GuildCheck ID/region và TTS read-name/rejoin đồng thời không mất edit độc lập.
- Onboarding marker giữ identity với submitted/approved/rejected title; concurrent apply không duplicate report; approval view states riêng từng message. Nickname format 2000/2005/2010/2015/2024 đúng.
- Translator cache miss fetch/unarchive/reuse mapped thread; hai request cùng message chỉ create một thread, mapping khác vẫn được giữ qua async storage thật.
- Attachment download thứ hai lỗi không delete proof gốc.
- CoreBank/GuildCheck initial ACK trước 100ms khi callback I/O vẫn pending sau 3.2s.
- Flask reload handler: thiếu/sai auth không dispatch; valid bearer dispatch. Heartbeat lấy readiness mỗi tick.

## 4. API handlers và browser UI thật

Node smoke chạy actual TypeScript handlers/proxy với auth/DB boundaries synthetic; DB transaction semantics được chứng minh riêng ở mục 2:

- CoreBank GET/PATCH token redaction, preserve omitted token, canonical guild; 401/403 writes; authenticated reload cả main bot và chatbot. Saved-but-not-applied trả 502, không báo applied giả.
- Modules/config/AI partial persistence giữ fields khác; bot-status/overview lỗi không trả empty success. Blacklist actor/guild lấy server/session, không dùng body spoof.
- Browser homepage chưa login không fetch blacklist trái phép; login dùng same-origin API, logout xóa rows đã thấy.
- Badge đọc `main_bot`: online/offline đúng; HTTP500 hiện unknown, không offline giả.
- CoreBank input không render token cũ; rapid autosaves serialize (max concurrent writes 1), final user intent giữ đúng, reload failure có toast sau khi lắp Toaster.
- Overview HTTP500 hiện lỗi thật. Module state unknown khi overview load lỗi, control disabled thay vì coi off.
- **Bundle cuối:** toggle response `saved:true, applied:false` giữ persisted OFF, header **0/1 module đang bật / Đã Tắt**, surfaces reload error; overview remount đọc activity mới **Persisted module change**. Đã quan sát screenshot actual UI và đóng tab.
- Public Flask command search tìm thấy `/guildmembers`, `/guildaudit`, `/utconfig`, `/utstatus` với inventory hiện hành; không re-pin incidental command-count tests.

Các screenshots đã được chụp/quan sát trong verification; không thêm screenshot hoặc fixture vào asset sản phẩm.

## 5. Tài liệu và tài nguyên tạm

README, architecture/storage/helper/deployment docs, onboarding/translator feature docs, env examples và timeline đã cập nhật. Plan lịch sử giữ nguyên; task matrix/walkthrough lưu tại thư mục này. Throwaway scripts, dependency/build copy và disposable PostgreSQL được dừng/dọn sau verification; không đưa vào commit. Local `.agents/skills/`, `.codex/`, `.env` và dữ liệu user không stage.

## 6. Điều kiện vận hành còn thiếu

Đã kiểm tra availability theo **tên biến, không đọc/in giá trị**: `SUPABASE_ACCESS_TOKEN`, `RENDER_API_KEY`, `VERCEL_TOKEN` không có trong environment công cụ. Không suy ra mọi provider login/CLI đều không tồn tại; chưa có bằng chứng về quyền quản trị hoặc thực hiện rotate/rollout được phê duyệt.

Cần operator thực hiện/xác nhận:

1. Rotate DB credential từng lộ, đồng bộ secret hiện hành, chứng minh credential cũ mất hiệu lực; xóa source không xóa Git history.
2. Backup hợp lệ rồi áp DDL versioned đã kiểm chứng; không dùng operational dump migration. Đối soát unknown/legacy financial records với evidence bên ngoài.
3. Canonical guild và WEBHOOK_SECRET đồng nhất; repo Chatbot riêng có authenticated receiver tương thích. HTTP reload accepted chưa chứng minh listener đã reload xong.
4. Deploy các ứng dụng liên quan và xác nhận log/health/gateway readiness, reload và workflows trên production.

Không đánh dấu mục tiêu tổng thể complete trước evidence cho các điều kiện này.

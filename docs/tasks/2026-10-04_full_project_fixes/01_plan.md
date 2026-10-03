# Implementation plan — sửa toàn bộ F01–F36 theo phương án 1

Ngày: 2026-10-04.
Trạng thái: phương án 1 đã được user chốt; implementation plan này đang chờ chốt trước khi sửa code.
Phạm vi: đủ 36 findings của review toàn workspace, không chỉ diff mới pull và không chỉ P1.

## 1. Mục tiêu và tiêu chí hoàn thành

- Đóng từng F01–F36 bằng thay đổi thực và bằng chứng phù hợp; không đánh dấu hoàn tất chỉ vì compile hoặc mock trả success.
- Giữ tính năng/lệnh hiện tại, sửa đúng root cause và migrate mọi caller chịu ảnh hưởng. Không thêm compatibility shim, placeholder, retry mù hoặc fallback giả.
- Không mất party/template khi restart hoặc DB lỗi; không mất/nhân đôi điểm SP; không claim Core thành công khi chưa thanh toán; hoàn tác đúng amount đã cộng.
- Không lộ bank token/DB credential; webhook không auth không được dispatch; dashboard và bot dùng cùng guild/schema/cache/reload contract.
- Bot I/O không chặn asyncio; interaction được ACK đúng hạn; trạng thái online phản ánh Discord gateway, không chỉ web service còn sống.
- Bootstrap/migration chạy thật trên PostgreSQL cô lập, transactional và có thể áp lại mà không ghi đè dữ liệu đã có.
- Smoke các đường lỗi đã review, regression tests cho invariant/concurrency/transition quan trọng, Python syntax, bot suite, TypeScript/build và UI thật đều có kết quả được ghi lại.
- Tài liệu/config examples/callers/tests đã được cập nhật; commit chỉ các file của đợt sửa, message tiếng Việt, không thêm Co-Authored-By.
- Nếu rotate credential hoặc deploy/config production chưa thực hiện được bằng quyền quản trị có sẵn, ghi rõ phần chưa hoàn tất và giữ mục tiêu mở; không coi sửa source là đã thu hồi secret hay đã rollout production.

## 2. Trạng thái và bằng chứng hiện tại

- Workspace `main` đã pull tới `7314c93` trước review; kiểm tra đầu bước plan không có tracked local changes. `.agents/skills/` và `.codex/` là file local của user, không sửa/stage.
- Review đã có 36 findings; F11 được tổng hợp ở mức P2 thay vì P1 vì ảnh hưởng badge trạng thái.
- Bot tests đã chạy trước khi lập plan dưới guard dotenv/network: 25 passed, 1 failed tại `test_public_index.py:142` vì inventory command khóa cứng.
- Smoke trước sửa tái hiện watchdog TypeError, Massing clear ngay sau restore, ledger Core khi thiếu token, delete ảnh gốc sau tách lỗi, SP metadata ghi trước economy lỗi, năm sinh format sai, webhook không auth vẫn dispatch.
- Các kết quả trên là baseline, không phải verification sau sửa. Không rerun chỉ để xác nhận lỗi đã biết; tái hiện bổ sung khi cần đánh giá edge chưa được exercise.
- Có Python, Node/npm, psql/postgres/initdb local để kiểm chứng offline. Không khởi động Discord bot thật.

## 3. Ràng buộc an toàn

1. Không chạy `bot/main.py`, không gọi Discord gateway thật, UnbelievaBoat thật hoặc ghi dữ liệu vận hành để test.
2. Chặn dotenv và outbound network trước import trong test harness; dùng credentials giả, PostgreSQL disposable và integrations giả ở boundary.
3. Không sửa/xóa dòng có sẵn trong `.env`. Nếu cần cấu hình mới, chỉ append có chủ đích, không in secret và đồng bộ `.env.example` tương ứng.
4. Dữ liệu JSON vận hành đi qua `bot/core/storage.py`; không test bằng cách sửa trực tiếp `json_storage`; không đặt scaffold/test/log vào `bot/Storage/`.
5. Schema được quản lý bằng DDL/versioned migration trong `scripts/`, qua cơ chế `scripts/db-exec.js` cho production khi đủ điều kiện. Không chạy lại data dump như một migration bootstrap.
6. `scripts/migration.sql` hiện chứa cả DDL và UPSERT snapshot dữ liệu. Không áp file này lên production trong đợt sửa: có thể lùi watermark và ghi đè số dư/config. Chuyển hướng dẫn và caller sang schema-only bootstrap/versioned migration; giữ snapshot lịch sử không được startup/migration hiện hành gọi.
7. Không tự sửa lịch sử Git để xóa secret, không tự rotate bằng endpoint chưa xác thực, không suy đoán quyền truy cập Render/Vercel/Supabase.
8. Trước đổi exported APIs, dùng LSP references nếu server available; đọc đầy đủ caller trước cutover. Agent không chạy build/lint/test/formatter giữa chừng; integration owner chạy lượt verification tổng hợp sau edits.

## 4. Thiết kế chung và contract cần chốt

### 4.1 DB/storage/cache: async, fail rõ ràng, không ghi state chưa load

- Dùng một boundary I/O awaitable nhất quán cho runtime bot. Backend Supabase sync được chạy ngoài event loop bằng executor/to_thread; snapshot payload trước khi chuyển thread, timeout client thật và khởi tạo client thread-safe.
- Giữ sync API chỉ nếu còn caller sync thực trong helper; không giữ alias/re-export chỉ để tránh migrate. Migrate mọi cog, heartbeat, logger, sync, config load/save và tests chịu ảnh hưởng.
- Không query DB trong constructor đồng bộ của cog; load config/state trong lifecycle async và await trước nhận sự kiện cần state đó.
- Storage phân biệt row không tồn tại với request lỗi. Default chỉ hợp lệ cho row không tồn tại; lỗi mạng/DB được truyền lên caller và chặn ghi snapshot chưa load thành công.
- Không mutate state authoritative/cache rồi báo thành công khi persist lỗi. Dirty state cần retry vẫn được giữ; lỗi hiển thị cho consumer nhưng không nuốt rồi báo success.
- Reload invalidates cache phù hợp rồi await đọc mới. Không giữ cache default phát sinh từ request lỗi như config thật.
- Các interaction có DB/network I/O: authorize/validate nhanh, defer trước I/O, sau đó dùng followup/edit response. Đường send_modal preload/cache dữ liệu, không defer rồi cố send_modal.

### 4.2 Secret và webhook

- `WEBHOOK_SECRET` là secret server-side chung giữa bot và dashboard; không dùng prefix `NEXT_PUBLIC_`, không đưa vào JSON/log/browser.
- Dashboard gửi secret trong Authorization header; Flask kiểm tra constant-time, fail-closed khi thiếu/sai secret và chỉ dispatch sau xác thực. Secret thiếu là cấu hình lỗi, không tự bật chế độ public fallback.
- GET/PATCH CoreBank không trả raw `unbelievaboat_token`; response dùng cờ `token_configured`. Admin gửi token mới qua PATCH khi muốn thay; bỏ trường token nghĩa là giữ nguyên, không ghi empty vì UI nhận response đã redact.
- Giữ admin guard ở proxy và route ghi. Authenticated non-admin chỉ thấy response đã lọc; không biến việc ẩn input thành cơ chế bảo mật.
- Script DB lấy URL từ env và không log URL/exception có credential chưa redact.
- Credential hard-code đã bị lộ phải được thu hồi/rotate bởi quyền quản trị thực; xóa literal trong source không đủ. Thay đổi auth webhook cần secret khớp trên cả deployments trước rollout.

### 4.3 Core ledger: durable state, snapshot amount, không hứa exactly-once API ngoài

- Validate channel/Officer/recipient/token trước claim. Ledger unique theo credit key hiện tại, claim/transition conditional atomic tại DB; query/claim lỗi hoặc duplicate không được tiếp tục gửi PATCH.
- Persist guild, Officer, recipient, amount và thông tin emoji tại thời điểm claim; revert đọc snapshot, không đọc giá/emoji hiện tại.
- Lifecycle rõ ràng: claim/pending → credited; credited → reverting → reverted. Lỗi có kết quả xác định không được để record giả thành công; kết quả thanh toán chưa biết giữ trạng thái cần đối soát, không xóa dấu vết.
- HTTP response thành công mới được xác nhận credited/reverted. Revert lỗi giữ quyền đối soát/retry an toàn, không delete ledger trước fetch/API.
- Không tự resend khi timeout/connection reset/5xx hoặc crash sau gửi mà chưa persist kết quả: provider có thể đã đổi balance. Chỉ dedupe DB không tạo transaction atomic giữa PostgreSQL và API ngoài.
- Trước implement, đối chiếu contract chính thức của provider về idempotency/transaction history. Nếu provider hỗ trợ idempotency, dùng đúng contract thực; nếu không, lưu trạng thái unknown và thực hiện reconciliation có xác nhận kết quả thực, không giả fallback exactly-once.
- Record legacy chỉ có Officer/amount chưa đủ chứng minh recipient hoặc thanh toán thành công: giữ dữ liệu cũ, đánh dấu chưa đối soát khi cần; không tự cộng/trừ lại để “backfill”. Đối soát không chạy trong tests và không sửa số dư production tự động.
- Reconciliation cần được implement thực cùng đường vận hành có kiểm chứng. Nếu cần helper, đặt `scripts/`, chạy explicit, yêu cầu tham chiếu ledger và bằng chứng/decision từ người có quyền; không thêm slash command ngoài phạm vi nếu không cần.

### 4.4 SP: transaction DB thật và watermark độc lập thứ tự file

- Parse toàn bộ dòng hợp lệ; loại dòng timestamp/amount không hợp lệ trước khi tính max watermark. Không dùng dòng đầu làm mốc.
- Runtime gửi các delta/log rows tới RPC PostgreSQL; function lock watermark `sp_metadata` trong transaction, chọn dòng mới theo watermark đã lock, cộng delta vào economy, insert history và tiến watermark cùng transaction.
- Retry/reupload sau commit không cộng lại overlap. Hai upload concurrent không cùng đọc watermark cũ rồi ghi đè; constraint lỗi rollback cả ba phần.
- Lệnh sửa điểm/reset hiện tại được migrate nếu cần để không ghi whole snapshot cũ đè transaction mới; không thêm tính năng scoring khác.
- Giữ schema/key semantics hiện tại trừ phần migration cần thiết; không tự đổi toàn bộ scoring sang per-guild hoặc backfill dữ liệu vận hành.

### 4.5 Dashboard autosave: changed fields, không ghi whole snapshot

- PATCH scalar fields thay đổi; server whitelist writable fields, lấy guild/actor từ config/session, không cho body override identity.
- Token bỏ qua trong request phải giữ nguyên. Emoji được cập nhật theo key/operation atomic ở DB thay vì overwrite whole map từ snapshot cũ; thay đổi arrays/scalar ở AI chỉ ghi field đã chỉnh.
- Serialize edits trong một page theo thứ tự user; consumer error/conflict không báo đã lưu. Không chỉ bỏ qua response cũ vì request cũ vẫn có thể đã overwrite DB.
- Hai editor thay hai field/emoji key riêng không làm mất nhau; cùng field theo write order thực, không giả merge quyết định khác nhau của hai người.
- API module/config/CoreBank dùng chung authenticated webhook contract. Persist thành công nhưng reload lỗi phải trả tín hiệu rõ là bot chưa áp dụng, không báo “đã áp dụng” giả.

### 4.6 Migration và rollout

- Tạo bootstrap schema-only đầy đủ khớp producers/consumers hiện tại; bảng runtime gồm guild/AI/core configs, activity/economy/SP metadata/SP transactions, Core ledger, TTS config, JSON storage, channels/roles, blacklist/system logs và bảng legacy còn caller thực.
- DDL cụ thể cho Core state/recipient/snapshot, SP RPC, atomic config map operations được version hóa trong migration mới. Không truncate/drop bảng hoặc seed đè dữ liệu.
- Script apply gửi toàn SQL transactional hoặc driver hỗ trợ multi-statement/dollar-quote; không tự split `;`, không chỉ print lỗi rồi tiếp tục làm schema từng phần.
- FK/index/RLS áp sau CREATE TABLE; policy service_role, khóa quyền execute RPC phù hợp backend và admin handlers. Bảng/column dùng `system_logs`, `user_economy`, `source_guild_id`, không dựng bảng rỗng khác chỉ để query cũ hết lỗi.
- Schema chạy được trên DB rỗng và DB có synthetic legacy rows; áp lại không reset watermark/balance hoặc nhân đôi constraints/triggers.
- CoreBank bỏ khóa `default` trong runtime; chuyển legacy row sang guild thật có kiểm tra conflict, không overwrite row guild đã có hoặc map nhầm dữ liệu của repo chatbot.
- Triển khai theo thứ tự: backup qua cơ chế hợp lệ → DDL additive đã verify → cấu hình secret hai phía → deploy bot/dashboard cùng contract → kiểm tra health/đường đã đổi. Không dùng rollback code cũ làm lý do xóa ledger mới.
- Production DDL/config/deploy chỉ được kết luận đã làm khi có output thật. Nếu quyền tích hợp không có, giữ mục tiêu mở và ghi rõ thao tác thiếu; không mở bot local thay production.

## 5. Thứ tự thực hiện và ownership

### Giai đoạn A — bảo mật và nền tảng an toàn

- F12, F07, F35, F26; sửa secrets/response/webhook/test isolation trước.
- Chuẩn hóa DB async và lỗi storage/cache F17/F20, schema bootstrap/apply F13/F28 là prerequisite cho ledger và dashboard fixes, không chờ đến cuối chỉ vì thuộc scripts.
- Integration owner chốt interface awaitable/schema/webhook/PATCH và migration order trước khi phân việc.

### Giai đoạn B — mất dữ liệu và tiền/điểm

- F01/F02 runtime/restart; F03/F04/F05 Core; F19/F25 SP; F32 activity.
- Không triển khai code phụ thuộc RPC/column trước migration schema đã kiểm chứng.

### Giai đoạn C — Discord workflow và contract dashboard

- Onboarding/Massing/TTS/Translator F21/F22/F23/F24/F27/F33/F34/F36.
- Dashboard guild/cache/reload/status/data/save F06/F08/F09/F10/F11/F14/F15/F16/F31.

### Giai đoạn D — helpers, inventory và verification tổng hợp

- F18/F29/F30, docs/schema instructions/config examples liên quan.
- Chạy checks/smoke/regressions và ghi bằng chứng từng F; commit logical groups sau khi phần liên quan được integration verify, không commit code chưa kiểm chứng.

Nếu phân việc song song sau khi plan được chốt:

- Integration owner: shared DB/storage/cache API, schema migrations, webhook contract, integration/verification/docs.
- Financial slice: CoreBank + Siphoned và regressions ledger/SP; không tự sửa shared API/schema mà chưa chốt contract.
- Discord workflow slice: main/Massing/onboarding/LastSeen/TTS/translator; giữ owner từng file và báo dependency schema.
- Dashboard slice: API/UI/auth/PATCH/reload/status; dùng shared schema/webhook contract, không sửa bot.
- Helper slice nếu độc lập đủ lớn: path/env/apply helpers và auxiliary instruction; không sửa schema của integration owner.
- Mỗi task skip build/lint/tests/formatters giữa chừng; verification được chạy một lượt tổng hợp sau khi tasks tích hợp. Không spawn thêm worker chỉ để làm một thay đổi nhỏ.

## 6. Ma trận đầy đủ F01–F36

Mỗi dòng là một deliverable riêng. File ghi dưới đây là target chính, không miễn migrate caller khác chịu ảnh hưởng.

| ID | Thay đổi/files chính | Tiêu chí kiểm chứng |
|---|---|---|
| F01 | `bot/main.py`: mốc watchdog None, một task duy nhất và cancel đúng lifecycle. | Chuỗi khỏe → disconnect → reconnect → disconnect không TypeError; restart chỉ sau ngưỡng; reconnect/on_ready không tạo watchdog trùng. Không kill process thật trong smoke. |
| F02 | `bot/cogs/massing.py`: start cleanup dù state rỗng, delay lần clear đầu và preserve restored parties. | Restore 1 party không bị xóa tick đầu; party mới sau startup rỗng vẫn có cleanup; trước hạn giữ state, đến hạn clear/persist đúng. |
| F03 | `bot/cogs/corebank.py`, ledger DDL/state transitions. | Thiếu token không claim; duplicate/DB error không PATCH; API lỗi không record success; concurrent Officers chỉ một claim; refund lỗi giữ ledger; unknown outcome không resend mù. |
| F04 | CoreBank refund dùng ledger amount/recipient/emoji snapshot. | Cộng 100 rồi đổi config 200 vẫn refund 100; emoji bị xóa vẫn có thể xử lý record đã credited; không dùng Officer làm recipient. |
| F05 | CoreBank attachment split/delete. | Attachment thứ hai/to_file/send lỗi giữ gốc; tất cả repost thành công mới delete; không mất bằng chứng vì bot vẫn có Manage Messages. |
| F06 | `bot/core/config_store.py`, CoreBank reload listener. | Backend A → B → authenticated reload làm cog dùng B; lỗi reload không thay B bằng cache default và không báo success giả. |
| F07 | CoreBank API + page secret representation. | Non-admin/admin GET và PATCH response không lộ raw token; edit channel/emoji giữ token chưa gửi; unauthorized write vẫn 401/403. |
| F08 | CoreBank route guild config, migration row legacy. | Env chỉ có DISCORD_GUILD_ID: web/bot dùng cùng row; row default migrate không đè row guild đã tồn tại; không body override guild ID. |
| F09 | `api/modules` và các callers reload. | Toggle persist rồi bot reload đúng trạng thái; webhook lỗi được surfaced, không toast “đã áp dụng” trong khi RAM cũ. |
| F10 | `bot/core/heartbeat.py`. | Ready online; disconnected/not-ready offline dù loop còn chạy; freshness timeout vẫn có tác dụng; reconnect online trở lại. |
| F11 | `StatusBadge.tsx` và mọi consumer `/api/bot-status`. | Fixture thật shape main_bot/chatbot: badge render đúng từng trạng thái, không lấy top-level fields; API 401/5xx không bị coi success/offline authoritative. |
| F12 | `scripts/create_tables.py` env + redacted logging. | URL lấy từ env giả; không source literal credential hay log password; thiếu URL fail rõ trước connect; credential exposed được đánh dấu chưa thu hồi cho tới có evidence rotate. |
| F13 | `scripts/apply_schema.py`, execution caller/schema docs. | PostgreSQL nhận nguyên function/DO dollar-quote/comment/semicolon; lỗi giữa migration rollback, exit nonzero; import script không tự áp schema. |
| F14 | Blacklist API + page audit metadata. | FK source_guild_id khớp guild row thật; actor từ session; valid admin add thành công trên disposable schema; body spoof identity không được dùng. |
| F15 | Homepage blacklist fetch/session lifecycle. | Browser không gọi localhost/Flask để lấy blacklist; sau login tải đúng same-origin; 401 trước login không kẹt state sau login. |
| F16 | `api/overview` query/aggregate/error handling. | Seed system_logs/user_economy/blacklist synthetic hiện đúng activity/SP/count; không đọc bảng/column sai; DB lỗi không trả empty success giả. |
| F17 | DB/storage/config APIs + toàn runtime callers. | DB fake chậm/retry nhưng coroutine ticker/gateway-like task vẫn tiến; timeout thực được cấu hình; no constructor blocking query; payload không đổi giữa thread write. |
| F18 | Migration/init helper paths và entry-point guards. | Chạy từ cwd root/khác đều tìm repo/bot/Storage; source thiếu fail rõ, không “migration completed” khi không làm gì; không ghi DB thật trong smoke. |
| F19 | SP RPC, parser/handlers/manual mutation callers. | Failure sau economy/history/metadata rollback toàn bộ; retry/reupload chỉ cộng một lần; concurrent imports và manual delta không mất điểm; success chỉ sau commit. |
| F20 | Storage load error/result propagation + Massing/templates/config users. | Missing row được init; SELECT timeout chặn overwrite; recovered backend vẫn giữ party/template cũ; failed startup không dùng empty blob để save party mới. |
| F21 | Massing join/move mutation order. | A đang giữ user, B đầy: chuyển thất bại giữ nguyên A/fills và persisted state; move thành công đúng một slot. |
| F22 | Onboarding stable application identity/state. | Submitted/approved/rejected đơn nhận ảnh/link mới không tạo report/Officer ping trùng; concurrent messages không tạo hai application reports. |
| F23 | Onboarding persistent per-message view state. | Restart với pending A/B; Accept A rồi Rename B không disable Accept/Reject B; rejected/approved state giữ đúng trong view của riêng message. |
| F24 | Translator stored thread fetch/cache/unarchive. | Mapping có archived thread nhưng cache miss: fetch/unarchive/reuse; không create_thread trùng; missing/deleted thread được xử lý theo lỗi thật. |
| F25 | SP parser/max watermark. | File ascending/descending cho cùng kết quả; overlap không cộng đôi; dòng amount invalid cuối không đẩy watermark bỏ qua dữ liệu hợp lệ về sau. |
| F26 | `bot/tests/conftest.py`, DB helper test isolation/entrypoint. | Test suite/helper import không read dotenv thật hoặc connect outbound; .env ở máy không khôi phục credentials test đã disable; fake missing-client behavior được exercise. |
| F27 | Massing role/component validation trước state mutation. | Boundary vừa đủ component tạo view; vượt limit 25 hoặc custom_id limit báo lỗi, không orphan party hoặc persist invalid state; giữ UI chọn slot hiện có. |
| F28 | Bootstrap schema-only + versioned migrations + DATABASE_ARCHITECTURE. | DB rỗng tạo đủ bảng/FK/index/RLS/RPC; synthetic legacy schema upgrade; apply lại không reset balances/watermark; không dùng data dump để bootstrap. |
| F29 | Auxiliary AI helper instruction CLI/env/path + README. | Template fixture bên ngoài repo được đọc; missing path fail rõ trước API/menu; không mở file removed và không dùng instruction placeholder. Không gọi provider thật. |
| F30 | Public command inventory + `test_public_index.py`. | Public page phản ánh lệnh hiện tại; bỏ tests khóa cứng wording/count/copy/source text, không re-pin sang 38; giữ tests behavior consumer quan trọng; suite không fail vì lệnh hợp lệ mới. |
| F31 | CoreBank/AI PATCH + autosave consumers + atomic emoji update. | A/B edits khác fields đến ngược thứ tự không mất nhau; hai editor sửa emoji keys khác nhau không overwrite; same-page writes serialize; token omitted giữ nguyên; failures/conflicts không báo saved. |
| F32 | LastSeen dirty/save result and lifecycle. | First flush fail, không có message mới, second flush retry được; dirty clear chỉ khi mọi chunk thành công; shutdown/restart không giả success. |
| F33 | `_format_yob` và nickname consumer. | 2000→2k, 2005→2k5, 2010→2k10, 2015→2k15, 2024→2k24; nickname length vẫn đúng; malformed input giữ behavior hợp lệ. |
| F34 | TTS queue item/source channel + voice move/session. | Move A→B không đọc backlog A ở B; moderator move cập nhật session; text từ channel không khớp không bị đọc nhầm; reconnect đúng channel giữ behavior. |
| F35 | Flask auth webhook + dashboard server callers + env examples. | Missing/wrong secret 401/403 và zero dispatch; missing server config fail-closed; valid secret dispatch; secret không đi browser/log; callers gửi đúng header. |
| F36 | Interaction lifecycle toàn handlers chịu DB/network trước ACK. | Inject I/O >3s nhưng initial ACK đã gửi trước; followup/edit đúng response state; modal paths không defer sai; unauthorized/validation errors vẫn phản hồi đúng. |

## 7. Verification thực, tests và bằng chứng

### 7.1 Python/runtime

- Dùng process môi trường cô lập, patch dotenv trước import, chặn outbound socket, không gateway/bot.run. SQL local là ngoại lệ network được cấp riêng cho disposable PostgreSQL, không credentials production.
- LSP diagnostics/references hỗ trợ cutover, nhưng không thay runtime verification.
- `python -m py_compile` mọi Python file đổi, redirect bytecode cache ra temp thay vì sửa repo.
- Chạy bot suite dưới shared isolation. Regression permanent chỉ cho bug có khả năng consumer gặp: ledger states/races/refund snapshot, SP atomicity/order/overlap, no-overwrite-on-load-error, restart cleanup, per-message views/slot transitions, dirty retry, TTS channel boundary, auth/ACK.
- Không thêm tests forward/mock echoes/line text/default incidental. Xóa tests hiện tại khóa wording/list/count implementation; không cập nhật literal 34→38 rồi coi đã sửa root test problem.
- Smoke bằng script throwaway gọi function/handler thật, integrations giả tại boundary; lưu kết quả cụ thể, không chỉ assert not-throw hoặc nonempty.

### 7.2 PostgreSQL

- Init/start cluster disposable trong temp bằng binaries đã có, Unix socket/port riêng và synthetic data; không dùng `.env` production.
- Apply bootstrap + migration mới + hardening trên DB rỗng, apply lại, và upgrade fixture legacy. Test thật rollback, FK, unique claim, RPC permissions, concurrent SP imports/config map mutations.
- Kiểm tra balance/watermark/history/state sau từng transaction lỗi, không chỉ schema parsing hoặc mocked query strings.
- Không dùng `json_storage` production để chứng minh storage; fixture isolated hoàn toàn.

### 7.3 Dashboard/API/UI

- Đọc Next.js version-local guides theo workspace rules trước viết code, không áp conventions cũ của middleware/auth.
- TypeScript/checks/build không dùng secrets production; browser chạy app thật với fake API/session responses ở test boundary, không thêm auth bypass/dev login vào sản phẩm.
- Exercise status badges, blacklist after login, CoreBank token-configured/edit giữ token, toggles/reload error, rapid autosave/two editor changes. Chụp surface thực và close browser tabs sau kiểm chứng.
- Route handlers được exercise với session/auth và Supabase disposable/fake boundary; kiểm chứng deny non-admin/redacted responses ngoài UI, vì ẩn input không chứng minh security.
- Report rõ phần UI với fake integration và phần database transaction thật; không gọi đó là production end-to-end nếu chưa deploy.

### 7.4 Tài liệu và commit

- Sau smoke, cập nhật README, DATABASE_ARCHITECTURE, feature docs, deployment instructions/env examples, public page inventory và `/aboutme` nếu inventory thay đổi. Không sửa tên/lệnh vô cớ.
- Lưu `02_task.md` với trạng thái F01–F36 và `03_walkthrough.md` với bằng chứng tại thư mục task này; không overwrite artifact của đợt khác.
- Remove throwaway scripts/test resources sau verify; helper vận hành thực đặt `scripts/`. Không dọn unrelated code của user.
- Commit các file trong scope đã verify, message tiếng Việt. Không stage local .agents/.codex, secret/env, generated files hoặc source của user khác.
- Không tự push/deploy khi chưa được yêu cầu hoặc khi integration prerequisite chưa đủ. Nếu push được yêu cầu, fetch trước; conflict dừng không resolve tùy tiện theo repo rules.

## 8. Những điều không được hiểu là đã hoàn tất

- Plan này không phải patch: hiện mới có artifact, chưa sửa product code hoặc database.
- Rotate credential exposed và cấu hình secret trên production là yêu cầu vận hành thực, không được đóng bằng việc sửa `.env.example`.
- Exactly-once giữa DB và API ngoài không thể suy ra từ unique ledger. Mọi unknown payment cần contract idempotency thực hoặc reconciliation thực.
- Đã chốt phương án không đồng nghĩa đã chốt implementation plan. Sau khi user chốt plan, bắt đầu thực hiện đủ ma trận trên, không tự bỏ F nào.

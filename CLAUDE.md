# CLAUDE.md

Xem [README.md](README.md) để biết tổng quan dự án, stack và cấu trúc code.

## Quy trình làm việc — QUAN TRỌNG NHẤT

Khi user đề xuất tính năng mới hoặc sửa đổi code: **bàn thiết kế trước** (mô tả lệnh, logic, ảnh
hưởng gì, file nào bị đụng) — KHÔNG viết/sửa code ngay.

Chỉ viết/sửa code khi user gõ RÕ RÀNG một trong các từ xác nhận: **"chốt", "ok", "oki", "ok làm đi", "làm đi",
"chốt code đi"**.

Các hành động sau KHÔNG tính là xác nhận: trả lời câu hỏi phụ, gửi ảnh/screenshot, cung cấp thêm
thông tin, hỏi ngược lại.

Nếu không chắc user đã chốt hay chưa, hỏi lại "Chốt chưa?" và chờ — tuyệt đối không tự ý code.

Ngoại lệ: các yêu cầu chỉ-đọc (đọc code, giải thích, đánh giá, tìm bug mà không sửa) không cần qua
gate này — chỉ áp dụng cho việc _viết/sửa_ code.

Quy tắc dấu hỏi: bất kỳ prompt nào kết thúc bằng dấu hỏi chấm `?` đều được coi là **câu hỏi /
thảo luận** — KHÔNG viết/sửa code, chỉ trả lời và trao đổi. Quy tắc này áp dụng ngay cả khi nội
dung câu hỏi liên quan đến code hoặc tính năng.

Sau khi code xong và pass `py_compile`: tự động `git add` + `git commit` luôn, không cần hỏi lại
"commit đi?" — user đã cấp quyền chuẩn.

Trước khi `git push`: đây là dự án dùng chung (có thể có người khác đã push thay đổi lên GitHub),
nên BẮT BUỘC `git fetch` rồi kiểm tra xem remote (`origin/<branch>`) có commit mới nào mà local
chưa có không.

- Nếu remote không có gì mới, hoặc có commit mới nhưng merge/rebase sạch không xung đột: push
  luôn, không cần hỏi lại.
- Nếu phát hiện xung đột (cùng sửa 1 đoạn code, hoặc merge/rebase báo conflict): DỪNG LẠI, KHÔNG
  tự ý resolve — báo rõ cho user biết file nào xung đột, xung đột với commit nào, và chờ user
  quyết định cách xử lý.

Sau khi push xong: kiểm tra xem máy local của user có đang chạy tiến trình bot thật không (vd
`ps aux | grep "bot/main.py"`), nếu có thì `kill` luôn tiến trình đó — tránh trường hợp bot chạy
song song cả ở local lẫn Render (xung đột Discord gateway, xung đột auto-sync Storage lên GitHub).

## Nguyên tắc code (Karpathy guidelines)

Sau khi đã "chốt", áp dụng 4 nguyên tắc này khi code:

1. **Nghĩ trước khi code** — không đoán mò, không giấu chỗ chưa rõ. Nếu có nhiều cách hiểu, nêu ra
   cho user chọn thay vì tự ý chọn 1. Nếu có cách đơn giản hơn cách user đề xuất, nói thẳng.
2. **Đơn giản trước tiên** — code tối thiểu đủ giải quyết đúng yêu cầu. Không thêm tính năng/
   abstraction/config chưa ai yêu cầu. Không xử lý lỗi cho tình huống không thể xảy ra.
3. **Sửa đúng phạm vi (surgical)** — chỉ đụng đúng chỗ cần sửa. Không tiện tay "cải thiện" code/
   comment xung quanh không liên quan, không refactor lan man. Giữ nguyên style hiện có. Chỉ dọn
   import/biến/hàm mồ côi do chính thay đổi của mình tạo ra — code chết có sẵn từ trước thì nêu ra
   cho user biết, không tự ý xóa.
4. **Làm theo tiêu chí kiểm chứng được** — biến yêu cầu mơ hồ thành tiêu chí rõ ràng, kiểm chứng
   được (vd: "sửa bug" → tìm cách tái hiện bug, sửa, rồi xác nhận hết bug thay vì chỉ sửa theo cảm
   tính).

## Về code

- Code ngắn gọn, đủ tính năng, không dài dòng thừa.
- Luôn check syntax (`python -m py_compile ...`) trước khi báo hoàn thành một thay đổi Python.
- Sau khi thêm tính năng mới hoặc fix bug trong `bot/`: cập nhật lại danh sách lệnh (bảng tính
  năng) trong README.md, và cập nhật `FEATURE_FIELDS` trong `bot/cogs/about.py` (bảng lệnh hiện
  trong `/aboutme`) nếu danh sách slash/prefix command thay đổi.
- Commit message do AI tạo (`git commit`) phải viết 100% bằng tiếng Việt (vd `sửa_lỗi(ai): ...`
  thay vì `fix(ai): ...`), khớp style hiện có trong git log.
- Khi tạo commit: KHÔNG thêm dòng `Co-Authored-By: Claude ...` vào commit message — user muốn
  GitHub chỉ hiển thị mình họ là tác giả, không hiện đồng tác giả "claude".
- TUYỆT ĐỐI KHÔNG chạy lệnh khởi động bot thật trên máy local của user (vd `python bot/main.py`,
  `python main.py`) — bot đang chạy 24/7 trên Render (production), chạy thêm 1 bản ở local sẽ
  khiến bot bị "chạy trùng" ở 2 nơi cùng lúc (xung đột kết nối Discord gateway, xung đột auto-sync
  Storage lên GitHub). Chỉ chạy các script test độc lập (vd `test_api_key/*.py`, `py_compile`,
  test suite trong `bot/tests/`) — không chạy chính bot.
- Cấu trúc bot: `bot/main.py` (entry point) + `bot/core/` (hạ tầng dùng chung: config, storage,
  permissions, webserver, database) + `bot/cogs/` (mỗi hệ thống tính năng — about, alo_tts, blacklist,
  corebank, guildcheck, lastseen, massing, onboarding, siphoned, sync — là 1 cog riêng).
  Sửa 1 tính năng thì chỉ đụng cog tương ứng.
- **Lưu ý:** Tính năng AI Chat (chat_ai, chat_logger, learning, item_albion, wiki) đã được tách sang repo riêng [TNC-Chatbot](https://github.com/kudominer/TNC-Chatbot) và deploy trên Render tài khoản riêng.

## Lưu trữ dữ liệu — QUY TẮC BẮT BUỘC (Supabase)

Dữ liệu vận hành thật của bot (dữ liệu người dùng, cấu hình guild, template, điểm số...) hiện được lưu trên
**Supabase** — bảng `json_storage`, khóa theo tên file, qua lớp `load_json()` / `save_json()` trong
`bot/core/storage.py`. Thư mục `bot/Storage/` là **legacy** từ thời lưu file JSON local (cơ chế sync
GitHub `GITHUB_SYNCED_FILES` đã bị bỏ, `sync_to_github()`/`restore_from_github()` chỉ là stub) — không
còn là nơi lưu dữ liệu vận hành thật.

### ⛔ TUYỆT ĐỐI KHÔNG được phép:

- Đọc/ghi dữ liệu vận hành bằng `open()` thuần hay gọi thẳng Supabase — phải dùng `load_json()` / `save_json()` từ `bot/core/storage.py`.
- Sửa/xóa dữ liệu trực tiếp trên bảng `json_storage` qua console Supabase để "test nhanh" — mọi thay đổi phải qua code.
- Đặt file tạm, file test, file log vào `bot/Storage/` — thư mục này không còn được sync nên dữ liệu đặt vào sẽ thất lạc.

### ✅ Tạo bảng/cột tự động (DDL qua script)
Khi cần thêm bảng hoặc cột mới, Agent KHÔNG cần mở SQL Editor thủ công. Dùng script:
`node scripts/db-exec.js "SQL_DDL_ở_đây"` (ví dụ: `ALTER TABLE x ADD COLUMN y text;`).
Script dùng `DATABASE_URL` từ `.env` (đã có sẵn, chứa mật khẩu DB) qua package `pg`.
- Yêu cầu: `npm install pg` (đã cài tạm khi test; nếu thiếu chạy `npm install pg --no-save`).
- Mọi thay đổi schema (tên bảng, cột, kiểu) vẫn phải mô tả vào file docs của tính năng theo quy tắc trên.
- KHÔNG dùng anon/service_role key qua REST để tạo cột (REST không hỗ trợ DDL) — luôn qua script này hoặc SQL Editor.

1. Mọi đọc/ghi dữ liệu phải qua `load_json()` / `save_json()` — không dùng `open()` thuần.
2. Nếu cần thêm **bảng mới trên Supabase**: mô tả schema bảng (tên bảng, cột, kiểu, khóa chính) vào file docs của tính năng, và KHÔNG đụng bảng `json_storage` ngoài qua `storage.py`.
3. Tên khóa/tên file vẫn theo pattern `tnc_<tính_năng>_v<số_version>` để dễ tra cứu trên Supabase.
4. Mọi thao tác DB phải kiểm tra `SUPABASE_URL` / `SUPABASE_ANON_KEY` tồn tại và bọc trong `try-except` (xem mẫu ở `bot/core/database.py`) để không crash trên CI.
5. Đọc file chi tiết [bot/Storage/README.md](bot/Storage/README.md) trước khi thay đổi dữ liệu.

## Skills & Agents có sẵn trong dự án

`.claude/skills/` — 16 skill từ [anthropics/skills](https://github.com/anthropics/skills) (chi tiết:
`.claude/skills/README.md`). Dùng khi task khớp mô tả:

- `algorithmic-art` — vẽ art sinh thuật toán bằng p5.js (seeded randomness, flow field, particle)
- `brand-guidelines` — áp màu/font thương hiệu Anthropic vào artifact
- `claude-api` — tra cứu Claude API/Anthropic SDK (model, giá, streaming, tool use, MCP, caching)
- `doc-coauthoring` — quy trình đồng viết tài liệu/spec/decision doc cùng user
- `docx` — tạo/đọc/sửa file Word (.docx/.dotx): mục lục, heading, tracked changes, ảnh, find-replace
- `frontend-design` — gợi ý thiết kế UI/thẩm mỹ không rập khuôn (typography, màu sắc)
- `internal-comms` — template báo cáo nội bộ, cập nhật lãnh đạo, báo cáo sự cố, FAQ
- `mcp-builder` — hướng dẫn xây MCP server chất lượng cao (Python FastMCP hoặc Node/TS)
- `pdf` — đọc/trích xuất/gộp/tách/xoay/watermark/điền form/OCR PDF
- `pptx` — tạo/sửa PowerPoint (.pptx/.potx), template, ghi chú diễn giả
- `skill-creator` — meta-skill để tạo/sửa/đánh giá skill khác
- `slack-gif-creator` — tạo GIF động cho Slack (đúng kích thước/tối ưu)
- `theme-factory` — áp theme màu/font có sẵn (hoặc tự tạo) cho artifact
- `web-artifacts-builder` — xây artifact HTML phức tạp nhiều component (React/Tailwind/shadcn)
- `webapp-testing` — test web app local bằng Playwright (screenshot, log, kiểm tra UI)
- `xlsx` — tạo/sửa spreadsheet (.xlsx/.xlsm/.csv/.tsv): công thức, format, chart, dọn dữ liệu bẩn

`.claude/agents/` — subagent riêng cho dự án, gọi qua Agent tool:

- `python-reviewer` — review code Python (bảo mật, PEP8, type hint, concurrency, code quality)
- `silent-failure-hunter` — săn lỗi nuốt exception / silent failure (vd: `except Exception: pass`)

## Project-Scoped Rules

### Quy tắc lưu trữ Rules/Yêu cầu mới
Khi có yêu cầu mới, rule mới hoặc chỉ dẫn từ người dùng (User Rules/Instructions), thay vì ghi vào file `.agents/AGENTS.md`, hãy ghi trực tiếp vào file [CLAUDE.md](file:/Bot_Albion_TNC/CLAUDE.md).

### Feature Documentation
Từ nay khi user mô tả tính năng mới trong quá trình phát triển, BẮT BUỘC phải tự động lưu mô tả cơ chế hoạt động và chi tiết cách hoạt động của tính năng đó vào một file riêng (vd: `docs/features.md` hoặc một markdown file tương ứng).
Việc này đảm bảo dữ liệu không bị thất lạc và có thể dùng trực tiếp để đưa lên web dashboard hoặc viết tài liệu hướng dẫn sau này.

### ⛔ Quy tắc BẢO VỆ file .env (TUYỆT ĐỐI)
- **KHÔNG BAO GIỜ xóa hoặc ghi đè dòng/biến trong file `.env`** của user.
- Mọi thay đổi cấu hình (thêm key, sửa biến) chỉ được **thêm MỚI** (append dòng mới hoặc thêm biến mới),
  **giữ nguyên** các dòng hiện có.
- Nếu cần đổi giá trị biến (vd `GEMINI_API_KEY`): **thêm 1 dòng mới có giá trị đúng** phía sau, KHÔNG sửa/xóa
  dòng cũ. (Python `dotenv` đọc dòng cuối cùng có tên biến → giá trị mới thắng, dòng cũ được giữ làm bản dự)
  phòng).
- Lý do: `.env` có thể chứa nhiều key/dự phòng do user tự quản, và việc xóa nhầm sẽ mất cấu hình không thể khôi phục.

### Quy tắc quản lý Script tiện ích (Helper/Hotfix)
Khi tạo các script tiện ích, script vá lỗi (helper/hotfix/utility scripts) phát sinh trong quá trình phát triển dự án, BẮT BUỘC phải đặt chúng vào thư mục [scripts/](file:///Users/twot/Documents/CODE/Bot_Albion_TNC/scripts) thay vì thư mục gốc (root directory). Việc này giúp giữ cho thư mục gốc luôn gọn gàng và dễ dàng tìm kiếm/tham khảo các script này khi cần.

### Ngôn ngữ & xưng hô

Giao tiếp bằng tiếng Việt xương hô theo cách người dùng gọi.
- Tuyệt đối làm theo đúng luồng: (1) Lắng nghe ý tưởng -> (2) Phân tích 3 phương án -> (3) Đợi user chốt -> (4) Lên Implementation Plan chi tiết -> (5) Đợi chốt plan -> (6) Code.
- Lưu ý về Implementation Plan: Mỗi khi có yêu cầu lên bảng kế hoạch (Implementation Plan), PHẢI tạo một file artifact mới hoàn toàn (ví dụ: `implementation_plan_v2.md`, `implementation_plan_featureX.md`). TUYỆT ĐỐI KHÔNG ghi đè lên bản cũ để lưu trữ lịch sử tất cả các bản plan.

### Lưu trữ Artifacts (Plan, Task, Walkthrough)
BẮT BUỘC: Khi hoàn thành một tính năng hoặc đợt cập nhật có sử dụng các file artifact (Implementation Plan, Task, Walkthrough), bạn PHẢI tự động copy các file này từ thư mục ẩn của IDE ra để lưu trữ vĩnh viễn vào dự án.
Để tránh làm rác thư mục, phải tuân thủ nghiêm ngặt quy tắc cấu trúc sau:
1. Tạo một thư mục con riêng biệt nằm trong `docs/tasks/` theo định dạng `<YYYY-MM-DD>_<Tên_Tính_Năng>` (ví dụ: `docs/tasks/2026-08-04_supabase_migration/`).
2. Lưu các file artifact vào thư mục đó và ĐỔI TÊN theo thứ tự hợp lý để dễ đọc:
   - `01_plan.md` (Từ Implementation Plan)
   - `02_task.md` (Từ Task list)
   - `03_walkthrough.md` (Từ Walkthrough)
Không bao giờ được ném chung một đống file ra ngoài thư mục gốc hay các thư mục dùng chung, cũng không được ghi đè/xóa bỏ tài liệu cũ.

### Thói quen (BẮT BUỘC TUÂN THỦ)

Từ những kinh nghiệm và lịch sử commit, AI phải luôn tuân thủ các thói quen sau khi làm việc trên dự án này:

1. **Cẩn tắc vô áy náy trên CI (Continuous Integration):**
   - Mọi đoạn code khởi tạo kết nối Database (Supabase, SQL), gọi API bên ngoài, hoặc sử dụng cấu hình nhạy cảm đều BẮT BUỘC phải được bọc trong khối `try-except`.
   - Phải kiểm tra sự tồn tại của biến môi trường trước khi khởi tạo để đảm bảo code không bao giờ crash (làm sập luồng test) trên môi trường CI (nơi thường không có sẵn file `.env`).

2. **Đồng bộ Config môi trường:**
   - Bất cứ khi nào thêm, xóa hoặc sửa một biến môi trường trong file `.env`, phải TỰ ĐỘNG cập nhật file `.env.example` tương ứng để đồng bộ cấu hình cho các thành viên khác trong team.

3. **Thẩm mỹ UI/Hình ảnh:**
   - Khi thiết kế giao diện (UI) hoặc tạo sinh/chọn hình ảnh (ví dụ: avatar bot, icon), luôn ưu tiên phong cách tối giản (minimalist), tinh tế, rõ ràng và không rườm rà.

4. **Phân biệt rạch ròi môi trường Local và Production (Render):**
   - Khi user báo lỗi chung chung (ví dụ: "bot không hoạt động", "bot sập"), LUÔN LUÔN mặc định đó là lỗi trên môi trường Production (Render).
   - TUYỆT ĐỐI KHÔNG tự ý chạy lệnh khởi động bot ở local để cố gắng tái hiện lỗi production. Việc này vừa vi phạm luật cấm chạy bot local, vừa dẫn đến kết luận sai lệch (ảo giác/hallucinate) do môi trường local chưa cấu hình đủ.
   - Cách xử lý chuẩn: Dừng lại và yêu cầu user cung cấp **Log mới nhất từ Render** hoặc nhắc nhở user kiểm tra xem đã **Redeploy** sau khi thay đổi biến môi trường hay chưa.

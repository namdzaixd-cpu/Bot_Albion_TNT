# Project Timeline — Bot Albion TNC

Nhật ký tiến độ và các mốc phát triển của dự án TNC Manager Bot.

---

## 📅 2026-10-04: Tích Hợp Nút Xác Nhận Nộp Đơn In-Game Vào Luồng Onboarding
- **Mục tiêu:** Yêu cầu thành viên xác nhận đã nộp đơn in-game Albion Online trước khi ping gọi Officer vào duyệt.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - `ApplyStep3Modal.on_submit`: Tạo Thread với Embed màu vàng hướng dẫn nộp đơn in-game và gắn view `ApplicantConfirmView` (nút `[Đã gửi apply ingame]`).
    - Phản hồi Ephemeral hoàn tất 100% kèm hướng dẫn 3 bước rõ ràng: (1) Mở game Albion apply ingame, (2) Vào thread, (3) Bấm nút xác nhận.
    - `ApplicantConfirmView.confirm`: Chỉ khi thành viên bấm nút xác nhận, bot mới chuyển sang trạng thái `⏳ Chờ duyệt`, ping `@Officer` và hiển thị bộ nút duyệt `OfficerApprovalView`.
- **Kết quả:** Code compile sạch sẽ, 66/66 unit tests passed, luồng onboarding chặt chẽ, loại bỏ hoàn toàn tình trạng ping sớm khi chưa nộp ingame.

---

## 📅 2026-10-04: Tối Ưu Giao Diện Chuyển Bước Onboarding (Embed Tiến Độ & Nút Bấm Rõ Ràng)
- **Mục tiêu:** Tối ưu hóa trải nghiệm chuyển tiếp giữa các bước 1 ➔ 2 ➔ 3 trong quy trình nộp đơn Multi-step Modal.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - Thêm Embed thanh tiến trình đo tiến độ trực quan (`33% ➔ 66% ➔ 100%`) sau mỗi lần gửi bước.
    - Cải tiến nút chuyển bước với nhãn to, rõ ràng (`👉 Bấm vào đây để điền tiếp Bước 2 / 3`, `📝 Bấm vào đây để hoàn tất Bước 3 / 3`).
    - Phản hồi hoàn tất đơn bằng Embed xanh lá chúc mừng kèm link điều hướng thẳng vào Thread bài nộp.
- **Kết quả:** Code compile sạch sẽ, 66/66 unit tests passed, giao diện nộp đơn mượt mà và trực quan.

---

## 📅 2026-10-04: Sửa Lỗi Nhận Diện ID Người Nộp Đơn (Tránh Bot Tự Đổi Tên & Tự Tag Mình)
- **Mục tiêu:** Khắc phục lỗi bot tự đổi tên và tag chính mình khi Officer duyệt đơn (do `thread.owner_id` trả về ID của Bot khi Bot tự tạo Thread nộp đơn).
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - `get_onboard_data`: Trích xuất `User: <id>` từ Footer hoặc Field `Người nộp` trong Embed; tự động loại trừ và chặn hoàn toàn `bot_id`.
    - `ApplyStep3Modal` & `_process_apply_thread`: Lưu trực tiếp `User: {user.id}` vào Footer của Embed đơn nộp.
    - `OfficerApprovalView`: Truyền `target_user_id` xuyên suốt các bước `approve`, `reject`, `rename_member` và chặn đổi tên/cấp role cho Bot.
  - `bot/tests/test_onboarding_logic.py`: Bổ sung test case kiểm tra chống gán nhầm ID bot (66/66 tests passed).
- **Kết quả:** Kiểm tra cú pháp và toàn bộ test suite vượt qua 100%, bảo đảm bot chỉ duyệt và đổi tên đúng thành viên nộp đơn.

---

## 📅 2026-10-04: Nâng Cấp Luồng Nộp Đơn Multi-Step Modal (12 Câu Hỏi) & Lệnh `/recuibot post_panel`
- **Mục tiêu:** Hiện đại hóa trải nghiệm nộp đơn gia nhập Guild TNC: tạo bảng thông báo có nút bấm và popup form điền 12 trường câu hỏi độc lập (chia làm 3 bước để vượt qua giới hạn 5 ô của Discord API), tự động tạo Thread và gắn bộ nút duyệt cho Officer.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - Xây dựng 3 Modal: `ApplyStep1Modal` (5 câu cá nhân), `ApplyStep2Modal` (5 câu kỹ năng/thiết bị), `ApplyStep3Modal` (2 câu mục tiêu & cam kết).
    - Xây dựng các View chuyển bước: `ApplyLaunchView`, `Step2LaunchView`, `Step3LaunchView` với state nháp `draft_applications`.
    - Thêm lệnh slash `/recuibot post_panel` cho phép Officer tùy chỉnh tiêu đề/mô tả và gửi bảng nộp đơn vào bất kỳ kênh nào.
    - Cho phép cấu hình kênh nộp đơn (`set_apply_channel`) hỗ trợ cả `ForumChannel` và `TextChannel`.
    - Đăng ký persistent view cho `ApplyLaunchView` trong `cog_load()`.
  - `bot/cogs/about.py` & `README.md`: Cập nhật lệnh `/recuibot post_panel`.
  - `bot/tests/test_onboarding_logic.py`: Bổ sung test Multi-step Modal và lệnh `post_panel` (65/65 tests passed).
  - `docs/features/onboarding_modal_apply.md`: Viết tài liệu đặc tả tính năng đầy đủ 12 câu hỏi.
  - `docs/tasks/2026-10-04_onboarding_modal_apply/`: Lưu trữ bộ task artifacts (01_plan, 02_task, 03_walkthrough).
- **Kết quả:** Kiểm tra cú pháp `py_compile` và test suite đạt 100%, quy trình nộp đơn đa bước trực quan và chuyên nghiệp.

---

## 📅 2026-10-04: Sửa Lỗi Tự Động Phản Hồi & Duyệt Đơn Apply (Onboarding)
- **Mục tiêu:** Khắc phục triệt để sự cố bot không tự động trả lời khi tạo bài viết mới trong kênh Forum Apply và các lỗi cấp Role/check quyền Officer.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - Bổ sung listener `on_thread_create`: Tự động `thread.join()` và đọc `starter_message` phản hồi ngay lập tức khi thành viên tạo thread.
    - Sửa `on_message`: Không chặn tin nhắn khi `thread.owner_id` chưa nạp cache (`None`).
    - Nâng cấp Regex trích xuất Ingame & Năm sinh tương thích với mọi định dạng markdown (`**Ingame:**`, `1. Ingame:`, `- Ingame:`).
    - Thêm fallback REST API `guild.fetch_member` trong `_get_member_or_fetch` để luôn tìm thấy thành viên khi cấp Role và Rename.
    - Mở rộng `check_officer_permission` chấp nhận quyền Administrator Discord, `officer_role_id` cấu hình và danh sách `is_officer`.
  - `bot/tests/test_onboarding_logic.py`: Bổ sung bộ unit tests cho Regex markdown và fallback permission (14/14 passed).
  - `docs/tasks/2026-10-04_fix_onboarding_apply/`: Lưu trữ bộ task artifacts (plan, task, walkthrough).
- **Kết quả:** Kiểm tra cú pháp `py_compile` và 64 tests bot đạt 100%, luồng duyệt đơn hoạt động tin cậy và tự động hoàn toàn.

---

## 2026-10-04: Sửa toàn bộ findings F01–F36

- Mã nguồn: ledger CoreBank/đối soát/refund snapshot, transaction SP, async DB/storage, reload/auth/cache/guild contract, restart/concurrency và interaction ACK.
- Dashboard: token redaction, serialized partial autosave, status/error states, same-origin blacklist và overview refresh sau partial apply.
- Kiểm chứng: 41 Python files compile; 61 tests pass; Next.js production build; PostgreSQL disposable rollback/concurrency/permissions; API handlers và browser UI thật với synthetic boundaries.
- Chưa rollout production hoặc xác nhận rotate credential đã lộ; không gọi bot/payment API thật và không thay `.env` production.
- [Ma trận F01–F36](tasks/2026-10-04_full_project_fixes/02_task.md), [bằng chứng và giới hạn](tasks/2026-10-04_full_project_fixes/03_walkthrough.md), [cơ chế vận hành](features/data_integrity_and_runtime.md).

---

## 📅 2026-09-22: Tối Ưu & Thu Gọn Luồng Apply Onboarding (In-Place Edit)
- **Mục tiêu:** Khắc phục tình trạng thread apply bị dài và spam 3-4 Embed duplicate bằng việc cập nhật tại chỗ trên đúng 1 tin nhắn duy nhất.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - `RulesConfirmView`: Chuyển sang `interaction.response.edit_message()` để chuyển bước nộp đơn in-game.
    - `ApplicantConfirmView`: Bỏ nút "Chưa gửi apply", edit tin nhắn cập nhật trạng thái chờ duyệt và chỉ gửi 1 dòng text ngắn ping Officer.
    - `OfficerApprovalView`: Edit tin nhắn cập nhật kết quả duyệt (Xanh lá) hoặc từ chối (Đỏ).
  - `docs/features/onboarding_streamline.md`: Tạo tài liệu luồng onboarding mới.
  - `docs/tasks/2026-09-22_onboarding_streamline/`: Lưu trữ bộ task artifacts.
- **Kết quả:** Code tối ưu, trải nghiệm apply mượt mà, thread gọn gàng.

---

## 📅 2026-09-22: Tính năng Tra cứu & Đối soát Thành viên Guild In-Game (Albion Online)
- **Mục tiêu:** Cho phép lấy dữ liệu danh sách thành viên Guild in-game từ SBI Official API, phân trang xem Fame và đối soát nhân sự In-game vs Server Discord.
- **Thay đổi chính:**
  - `bot/cogs/guildcheck.py`:
    - Bổ sung hàm `albion_get_guild_members(region, guild_id)` gọi REST API `gameinfo.albiononline.com`.
    - Tạo class `GuildMembersPaginationView` hỗ trợ duyệt danh sách qua các nút `⏮`, `◀`, `▶`, `⏭`.
    - Thêm lệnh `/guildmembers` với tùy chọn sắp xếp Fame / IGN và xuất file `.txt`.
    - Thêm lệnh `/guildaudit` (Officer) tự động đối soát chéo In-game vs Nickname Discord + đính kèm file báo cáo.
  - `bot/cogs/about.py`: Cập nhật bảng tính năng trong lệnh `/aboutme`.
  - `README.md`: Cập nhật mô tả hệ thống GuildCheck.
  - `docs/features/guild_members_audit.md`: Tạo tài liệu đặc tả tính năng.
- **Kết quả:** Kiểm tra cú pháp `py_compile` thành công, code chạy ổn định và tối ưu tài nguyên.

---

---

## 📅 2026-10-04: Nâng Cấp Hệ Thống Modal Onboarding 3 Bước & Tự Động Dọn Dẹp Ephemeral
- **Mục tiêu:** Mở rộng biểu mẫu nộp đơn gia nhập guild thành 12 câu hỏi đầy đủ chia làm 3 bước popup Modal (33%, 66%, 100%), tự động dọn dẹp các tin nhắn trung gian và bổ sung nút xác nhận nộp đơn in-game.
- **Thay đổi chính:**
  - `bot/cogs/onboarding.py`:
    - Tạo các class Modal: `ApplyStep1Modal`, `ApplyStep2Modal`, `ApplyStep3Modal` thu thập 12 trường thông tin.
    - Tạo các class View chuyển tiếp: `Step2LaunchView`, `Step3LaunchView`.
    - Cơ chế tự động dọn dẹp (Phương án 1): Gọi `delete_original_response()` xóa tin nhắn ephemeral của bước trước đó khi bước sau được nộp, và tự động thu hồi tin nhắn hoàn tất sau 60 giây.
    - Tích hợp nút `[Đã gửi apply ingame]` (`ApplicantConfirmView`) để ứng viên bấm sau khi đã nộp đơn in-game, gọi Officer duyệt.
  - `docs/tasks/2026-10-04_onboarding_ephemeral_cleanup/`: Lưu trữ tài liệu task artifacts.
- **Kết quả:** Kiểm tra cú pháp `py_compile` và test suite `pytest bot/tests` đạt 100% pass (66 passed).

---

---

## 📅 2026-10-10: Nâng Cấp Hệ Thống Massing CTA ZvZ & Hướng Dẫn Build Trang Bị
- **Mục tiêu:** Tích hợp bộ khung đội hình CTA 19 vị trí chuẩn của Guild TNC vào hệ thống Massing, giải quyết giới hạn 25 button của Discord bằng Dropdown Select Menu, tự động gửi hướng dẫn build đồ chi tiết cho từng slot và bổ sung nút tra cứu `🎒 Xem Build`.
- **Thay đổi chính:**
  - `bot/cogs/massing.py`:
    - Khai báo từ điển `CTA_BUILD_GUIDES` đầy đủ 19 slot thuộc 4 nhóm role (Tank, Support, Healer, DPS) với cấu hình chi tiết (Weapon, Armor, Hood, Shoes, Off-Hand, Cape, Food, Potion).
    - Tạo class `PartySlotSelect` dùng `discord.ui.Select` cho các party nhiều slot (> 12 slot).
    - Cập nhật `PartyView.rebuild_buttons` với cơ chế hybrid layout và bổ sung nút `🎒 Xem Build`.
    - Thêm cơ chế gửi Embed build đồ dạng Ephemeral khi thành viên pick slot hoặc bấm nút xem build.
    - Thêm slash command `/massing_cta [time] [note]` tự động điền sẵn Comp CTA 19 vị trí.
    - Tự động khởi tạo template `CTA TNC (Comp 19 Slot)` trong `cog_load()`.
  - `bot/cogs/about.py`: Bổ sung `/massing_cta` vào `FEATURE_FIELDS`.
  - `README.md`: Cập nhật tài liệu lệnh và tính năng Massing.
  - `docs/features/massing_cta_build_guide.md`: Tạo tài liệu chi tiết đặc tả tính năng.
  - `docs/tasks/2026-10-10_massing_cta_build_guide/`: Lưu trữ bộ artifacts (plan, task, walkthrough).
- **Kết quả:** Kiểm tra cú pháp `py_compile` pass 100%, party 19 slot hoạt động trơn tru trên Discord UI.

---

## 📌 Mục Bàn giao Bắt buộc (Mandatory Agent Handover)

### 1. Tình trạng hiện tại của dự án
- Bot đang hoạt động với cấu trúc Discord.py gồm các Cogs: `about`, `alo_tts`, `blacklist`, `corebank`, `guildcheck`, `lastseen`, `massing`, `onboarding`, `siphoned`, `sync`, `update_translator`.
- Dữ liệu lưu trữ qua Supabase (`bot/core/storage.py`).
- Cụm tính năng AI Chat đã được tách sang repo riêng `TNC-Chatbot`.
- Hệ thống Massing đã hỗ trợ hoàn hảo cả party PVP/PVE thông thường và đội hình **CTA ZvZ 19 slot** kèm **Build Guide** trang bị tự động qua lệnh `/massing_cta` và `/massing`.
- Đã test pass toàn bộ cú pháp qua `python -m py_compile`.

### 2. Bối cảnh & Dự định kế tiếp của user
- Hệ thống Massing CTA & Build Guide đã sẵn sàng phục vụ các buổi CTA của guild.
- Sẵn sàng tiếp tục phát triển các tính năng quản lý guild hoặc mở rộng theo yêu cầu tiếp theo của user.

### 3. Hướng dẫn kỹ thuật nhanh cho Agent tiếp theo
- Khi chạy kiểm tra cú pháp: Dùng `python -m py_compile bot/cogs/*.py`.
- **TUYỆT ĐỐI KHÔNG** khởi động bot thật ở local (`python bot/main.py`) vì bot đang chạy 24/7 trên Render.
- Đọc/ghi dữ liệu luôn thông qua `load_json()` / `save_json()` trong `bot/core/storage.py`.
- Tuân thủ quy trình làm việc (bàn thiết kế -> chốt -> plan -> chốt -> code) và SBI Compliance Policy.



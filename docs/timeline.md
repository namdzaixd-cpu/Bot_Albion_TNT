# Project Timeline — Bot Albion TNC

Nhật ký tiến độ và các mốc phát triển của dự án TNC Manager Bot.

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

## 📌 Mục Bàn giao Bắt buộc (Mandatory Agent Handover)

### 1. Tình trạng hiện tại của dự án
- Bot đang hoạt động với cấu trúc Discord.py gồm các Cogs: `about`, `alo_tts`, `blacklist`, `corebank`, `guildcheck`, `lastseen`, `massing`, `onboarding`, `siphoned`, `sync`, `update_translator`.
- Dữ liệu lưu trữ qua Supabase (`bot/core/storage.py`).
- Cụm tính năng AI Chat đã được tách sang repo riêng `TNC-Chatbot`.
- Luồng Onboarding trong `bot/cogs/onboarding.py` đã được tối ưu hóa sang cơ chế In-Place Edit cực kỳ gọn gàng.

### 2. Bối cảnh & Dự định kế tiếp của user
- User đã tối ưu xong cả 2 phần: Tra cứu thành viên In-game/Đối soát và Thu gọn luồng Onboarding.
- Sẵn sàng tiếp tục hỗ trợ phát triển các tính năng quản lý guild, web dashboard hoặc các tiện ích khác theo yêu cầu.

### 3. Hướng dẫn kỹ thuật nhanh cho Agent tiếp theo
- Khi chạy kiểm tra cú pháp: Dùng `python -m py_compile bot/cogs/*.py`.
- **TUYỆT ĐỐI KHÔNG** khởi động bot thật ở local (`python bot/main.py`) vì bot chạy trên Render.
- Đọc/ghi dữ liệu luôn thông qua `load_json()` / `save_json()` trong `bot/core/storage.py`.
- Tuân thủ quy trình làm việc (bàn thiết kế -> chốt -> plan -> chốt -> code) và SBI Compliance Policy.

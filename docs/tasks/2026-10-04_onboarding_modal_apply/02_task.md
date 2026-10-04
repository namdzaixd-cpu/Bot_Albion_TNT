# Task List: Onboarding Multi-step Modal Apply Flow

- [x] Thiết kế 3 Modal: `ApplyStep1Modal`, `ApplyStep2Modal`, `ApplyStep3Modal` trong `bot/cogs/onboarding.py`.
- [x] Thiết kế các View chuyển bước: `Step2LaunchView`, `Step3LaunchView`, và view panel gốc `ApplyLaunchView`.
- [x] Lưu trữ state nháp `draft_applications` an toàn theo `user_id`.
- [x] Tích hợp tra cứu SBI API khi nộp bước 3 và tự tạo Thread trong `ForumChannel` hoặc `TextChannel`.
- [x] Đăng ký persistent view cho `ApplyLaunchView` trong `cog_load()`.
- [x] Thêm slash command `/recuibot post_panel` cho phép Officer gửi bảng nộp đơn.
- [x] Cập nhật bảng lệnh `FEATURE_FIELDS` trong `bot/cogs/about.py` và bảng tính năng trong `README.md`.
- [x] Bổ sung unit tests cho Multi-step modal và post_panel command trong `bot/tests/test_onboarding_logic.py`.
- [x] Kiểm tra cú pháp bằng `py_compile` và chạy test suite `pytest bot/tests` (65/65 tests passed).
- [x] Tạo tài liệu tính năng `docs/features/onboarding_modal_apply.md`.
- [x] Cập nhật tiến độ vào `docs/timeline.md`.

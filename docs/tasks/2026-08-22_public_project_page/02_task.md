# Task Checklist — Guild Operations Dossier

Ngày thực hiện: 2026-08-22

## Đồng bộ và review

- [x] Fetch và fast-forward `main` tới commit nguồn `c4a3058`.
- [x] Review cấu trúc Bot, 9 cog production, Dashboard, AI Bot tách riêng và lớp lưu trữ Supabase.
- [x] Đối chiếu decorator để khóa ma trận đúng 34 slash command/subcommand.
- [x] Xác định các claim cũ phải loại bỏ: trạng thái Discord suy diễn, placeholder invite và GitHub JSON sync.

## Triển khai

- [x] Viết đặc tả `docs/features/public_project_page.md`.
- [x] Viết contract test trước và xác nhận test fail với giao diện cũ.
- [x] Đối chiếu 34 lệnh trong HTML với command tree được nạp từ đúng 9 extension production; mock toàn bộ đọc dữ liệu và task nền.
- [x] Thay `index.html` bằng Guild Operations Dossier tự chứa HTML/CSS/JavaScript.
- [x] Giữ nguyên placeholder runtime `{{ session_id }}` và kiểm thử qua Flask test client.
- [x] Thêm đủ 8 section nội dung, 9 cog, 34 lệnh, kiến trúc và luồng dữ liệu.
- [x] Thêm tìm kiếm, lọc module, `aria-live`, skip link, focus-visible và reduced-motion.
- [x] Không thay đổi command, cog, database, Dashboard, README hoặc `/aboutme`.

## Kiểm chứng

- [x] Contract test: 3 passed.
- [x] Toàn bộ Python test suite: 26 passed; còn 45 warning deprecation từ dependency hiện có.
- [x] `py_compile` toàn bộ Python trong `bot/`: OK.
- [x] Playwright desktop 1440×1000: không overflow, lọc/tìm kiếm đúng, không lỗi console.
- [x] Playwright mobile 390×844: không overflow, card/table responsive.
- [x] Keyboard: skip link là focus target đầu tiên.
- [x] Reduced motion: reveal animation không được kích hoạt.

# Walkthrough — Guild Operations Dossier

Ngày hoàn thành: 2026-08-22

## Kết quả

Trang Flask công khai đã được chuyển thành một hồ sơ vận hành duy nhất cho hai nhóm độc giả: thành viên Discord cần tra cứu bot và developer cần hiểu kiến trúc. Nội dung phản ánh source production tại commit review `c4a3058`, đồng thời giữ nguyên cơ chế session runtime của `bot/core/webserver.py`.

## Nội dung chính

- Hero giải thích bài toán guild operations và chỉ báo trung thực rằng web service đang phản hồi.
- Bản đồ module trình bày 7 nhóm lệnh, 2 dịch vụ nền và AI Bot đã tách repository.
- Sơ đồ Bot–Supabase–Dashboard–AI Bot mô tả đúng ranh giới hệ thống và API ngoài.
- Sáu workflow giải thích onboarding, Siphoned, Massing, Core-Bank, GuildCheck và ALO TTS.
- Ma trận có đúng 34 lệnh production, tìm kiếm toàn văn và lọc theo module ngay trên client.
- Phần data/resilience mô tả Supabase, lazy client, retry, heartbeat và config reload; không còn quảng bá JSON/GitHub sync legacy.
- Phần verification công khai các kết quả đã đo: 26 Python tests, `py_compile` thành công và Dashboard build 21 route.

## Thiết kế và khả năng tiếp cận

Visual direction là bàn tác chiến guild: nền deep steel, chữ parchment, brass cho hành động và cyan cho dữ liệu. Trang dùng HTML semantic, skip link, focus-visible, vùng kết quả `aria-live`, layout mobile dạng card và tôn trọng `prefers-reduced-motion`. Toàn bộ CSS/JavaScript nằm inline trong template như phương án đã chốt, không thêm dependency.

## Kiểm chứng đã chạy

```text
python -m pytest bot/tests -q
26 passed, 45 warnings

python -m py_compile <toàn bộ file Python trong bot/>
OK

Playwright — Chromium headless
desktop/mobile/filter/a11y/reduced-motion OK
```

Các warning còn lại là deprecation warning có sẵn từ `discord.py` và Supabase client trên Python 3.14, không phát sinh từ landing page.

Contract test không chỉ dùng danh sách hard-code: nó nạp command tree từ `TNCBot` với network, dữ liệu và background task được mock, rồi so qualified name của 34 command production với HTML. Trình duyệt Playwright riêng xác nhận JavaScript lọc đúng 5 lệnh Core-Bank và 7 lệnh ALO, cập nhật `aria-live` và không phát sinh console error.

## Phạm vi không thay đổi

Không sửa logic Discord, cog, command, database/schema, Dashboard, README, `/aboutme` hoặc dữ liệu Supabase. Những finding kỹ thuật ngoài landing page được giữ ngoài phạm vi thay đổi này.

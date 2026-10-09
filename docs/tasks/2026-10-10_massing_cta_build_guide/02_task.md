# Danh Sách Công Việc: Massing CTA & Build Guide

## 📋 Task Breakdown

- [x] **1. Phân tích & Thiết kế**:
  - [x] Trích xuất toàn bộ 19 slot CTA từ bảng hình ảnh của User.
  - [x] Đề xuất 3 phương án thiết kế và nhận xác nhận từ User (chọn Phương án 1).
  - [x] Lập Implementation Plan chi tiết.

- [x] **2. Cập nhật mã nguồn (`bot/cogs/massing.py`)**:
  - [x] Khai báo từ điển `CTA_BUILD_GUIDES` đầy đủ 19 cấu hình build (Weapon, Armor, Hood, Shoes, Off-Hand, Cape, Food, Potion).
  - [x] Thêm helper `get_build_guide()` và `build_guide_embed()`.
  - [x] Nới rộng `validate_party_layout()` hỗ trợ party lên tới 25 slot.
  - [x] Thêm class `PartySlotSelect` để chọn role/vũ khí qua Dropdown Select Menu khi party > 12 slot.
  - [x] Cập nhật `PartyView.rebuild_buttons` hỗ trợ layout hybrid (Buttons cho party nhỏ, Select Menu cho party lớn).
  - [x] Thêm nút `🎒 Xem Build` và callback `view_build_callback`.
  - [x] Cập nhật `make_join_callback` và `PartySlotSelect.callback` tự động gửi thông tin build guide khi join.
  - [x] Nâng cấp `MassingModal` hỗ trợ `prefill_name` và `prefill_time`.
  - [x] Tự động nạp template mặc định `CTA TNC (Comp 19 Slot)` trong `cog_load()`.
  - [x] Thêm slash command `/massing_cta`.

- [x] **3. Cập nhật tài liệu & Danh sách lệnh**:
  - [x] Cập nhật `FEATURE_FIELDS` trong `bot/cogs/about.py`.
  - [x] Cập nhật bảng tính năng trong `README.md`.
  - [x] Tạo tài liệu tính năng chi tiết `docs/features/massing_cta_build_guide.md`.
  - [x] Cập nhật `docs/timeline.md` và mục Handover.

- [x] **4. Kiểm thử cú pháp & Đóng gói**:
  - [x] Chạy `python -m py_compile bot/cogs/massing.py bot/cogs/about.py`.
  - [x] Lưu trữ bộ artifact vào `docs/tasks/2026-10-10_massing_cta_build_guide/`.

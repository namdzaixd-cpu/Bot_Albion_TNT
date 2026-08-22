# Guild Operations Dossier — Đặc tả trang giới thiệu công khai

Ngày chốt thiết kế: 2026-08-22

Phạm vi mã nguồn đã review: commit `c4a3058`

## 1. Mục tiêu

Thay trang giới thiệu Flask hiện tại bằng một **Guild Operations Dossier** công khai, giúp hai nhóm độc giả cùng hiểu đúng dự án:

- Thành viên và Officer Discord cần biết bot giải quyết việc gì và dùng lệnh nào.
- Developer cần thấy kiến trúc, luồng dữ liệu, stack, cách triển khai và mức độ kiểm chứng.

Trang có một nhiệm vụ duy nhất: trình bày trung thực, đầy đủ và dễ tra cứu về hệ sinh thái Bot TNC đang tồn tại trong mã nguồn production.

## 2. Sự thật nguồn phải phản ánh

- Bot chính chạy bằng Python, `discord.py`, Flask và được triển khai trên Render.
- `bot/main.py` nạp 9 cog: About, Siphoned, Massing, LastSeen, GuildCheck, ALO TTS, Core-Bank, Onboarding và Sync.
- Có 34 lệnh slash/subcommand đang được nạp. LastSeen và Sync là dịch vụ nền, không có slash command.
- `bot/cogs/blacklist.py` có trong repository nhưng chưa nằm trong `EXTENSIONS`; trang không được quảng bá các lệnh blacklist như lệnh đang hoạt động của bot chính.
- Dữ liệu vận hành nằm trên Supabase. `bot/Storage/` chỉ là legacy; GitHub JSON sync và cơ chế `.tmp/.bak` không còn là kiến trúc production.
- Dashboard Next.js dùng Discord OAuth và truy cập Supabase qua API server-side.
- AI Chatbot đã tách sang repository `https://github.com/kudominer/TNC-Chatbot` và chạy bằng bot/Render riêng.
- Flask `GET /` chỉ chứng minh web service đang phản hồi; nó không chứng minh Discord gateway đang online.
- `{{ session_id }}` phải được giữ để `bot/core/webserver.py` thay bằng session runtime.

## 3. Cấu trúc nội dung

Trang gồm các vùng sau, theo thứ tự:

1. Navigation: Tổng quan, Module, Kiến trúc, Lệnh, Công nghệ, cùng liên kết GitHub và Discord.
2. Hero: tên TNC Guild Manager, thông điệp quản trị guild Albion Online, trạng thái web service trung thực và session runtime.
3. Bài toán vận hành: onboarding, tổ chức lực lượng, điểm đóng góp, kiểm tra thành viên, voice và ngân quỹ.
4. Module: 7 nhóm lệnh người dùng, 2 dịch vụ nền và AI Bot tách riêng.
5. Architecture map: Discord ↔ Bot chính ↔ Supabase ↔ Dashboard, cùng AI Bot riêng và các API ngoài.
6. Luồng hoạt động tiêu biểu: onboarding, Siphoned, Massing, Core-Bank, GuildCheck và ALO TTS.
7. Command matrix: đủ 34 lệnh, lọc theo từ khóa hoặc module.
8. Data & resilience: Supabase, lazy client, retry 3 lần, heartbeat 60 giây, cache và reload cấu hình.
9. Stack & verification: Python/Discord/Flask, Supabase, Next.js/React và kết quả test/build đã xác minh.
10. Footer: repository bot chính, repository AI Bot, Discord TNC và Albion Online.

## 4. Ma trận 34 lệnh

| Module | Lệnh |
|---|---|
| About | `/aboutme` |
| Onboarding | `/recuibot toggle`, `/recuibot set_apply_channel`, `/recuibot setup_channels`, `/recuibot setup_roles`, `/recuibot list` |
| Siphoned | `/spupdate`, `/spcheck`, `/sphistory`, `/sptop`, `/splog`, `/spexport`, `/addsp`, `/removesp`, `/removesprole`, `/resetsp` |
| Massing | `/massing`, `/masstemplatelist`, `/masstemplatedelete` |
| GuildCheck | `/guildconfig`, `/guildcheck`, `/newmembers` |
| ALO TTS | `/alojoin`, `/aloleave`, `/alonametoggle`, `/alo`, `/aloconfig`, `/alomute`, `/alounmute` |
| Core-Bank | `/coresetup`, `/coreadd`, `/coreremove`, `/coreautoreact`, `/corelist` |

Mỗi lệnh phải có mô tả ngắn bằng tiếng Việt, badge module và thuộc tính `data-command` để test tự động xác nhận số lượng/độ duy nhất.

## 5. Hướng hình ảnh

Chủ đề là **bàn tác chiến của guild** thay cho landing page fantasy chung chung.

### Token màu

- Deep steel: `#101621`
- Panel steel: `#172334`
- Parchment text: `#E8E0CF`
- Guild brass: `#D2A84A`
- Map cyan: `#70B7C8`
- Battle red: `#B85745`

### Typography

- Display: Barlow Condensed, fallback `Arial Narrow`, sans-serif.
- Body: IBM Plex Sans, fallback system sans-serif.
- Command/data: IBM Plex Mono, fallback monospace.

### Dấu ấn

Architecture map mang hình “constellation operations map”: các node là Bot, Supabase, Dashboard và AI Bot; đường nối biểu thị luồng thật. Chỉ node trung tâm có chuyển động ambient nhẹ. Khi người dùng bật `prefers-reduced-motion`, toàn bộ chuyển động bị vô hiệu hóa.

## 6. Tương tác

- Navigation sticky, liên kết tới section bằng anchor.
- Ô tìm kiếm command lọc ngay trên client theo tên lệnh, module và mô tả.
- Nhóm chip module cho phép thu hẹp command matrix.
- Kết quả lọc cập nhật bằng vùng `aria-live`.
- Reveal-on-scroll chỉ là progressive enhancement; nội dung vẫn hiện nếu JavaScript không chạy.
- Không còn nút “Mời bot” vì chưa có client ID công khai hợp lệ. CTA chính là GitHub và Discord cộng đồng.

## 7. Accessibility và hiệu năng

- HTML semantic: `header`, `nav`, `main`, `section`, `footer` và heading theo thứ bậc.
- Có skip link, focus-visible rõ ràng, độ tương phản đạt mức đọc được trên nền steel.
- Command matrix đọc được bằng keyboard và không phụ thuộc hover.
- Mobile từ 320px không tràn ngang; bảng command chuyển sang card layout.
- Không dùng Font Awesome CDN. Icon dùng SVG inline/Unicode có `aria-hidden` khi chỉ trang trí.
- Font ngoài có fallback hệ thống; trang vẫn dùng được khi Google Fonts lỗi.
- Không tạo particle ngẫu nhiên hoặc animation dày đặc.

## 8. Trạng thái kiểm chứng công khai

Trang chỉ nêu các kết quả đã đo được ở commit review:

- 26 Python tests passed sau khi bổ sung 3 contract test cho landing page.
- Toàn bộ Python trong `bot/` qua `py_compile`.
- Next.js production build thành công với 21 route.

Không công khai chi tiết lỗ hổng, endpoint nội bộ, token, tên biến secret hoặc finding bảo mật từ audit.

## 9. Ngoài phạm vi

- Không sửa watchdog, blacklist cog, debug endpoint, webhook authentication hay dashboard lint trong thay đổi này.
- Không thêm API health/status mới.
- Không thay đổi database/schema, command hoặc logic Discord.
- Không sửa README hoặc `/aboutme` vì danh sách command không thay đổi.
- Không khởi động bot Discord ở local.

## 10. Tiêu chí hoàn thành

- Trang công khai mô tả đúng kiến trúc production và việc AI Bot đã tách repo.
- Có đủ 34 lệnh đang được nạp, không quảng bá lệnh của cog chưa được nạp.
- Không còn `YOUR_CLIENT_ID`, “BOT ONLINE”, GitHub Sync, JSON DB hay Auto Backup sai kiến trúc.
- Trạng thái web được diễn đạt trung thực và vẫn hiển thị session runtime.
- Responsive, keyboard-friendly, hỗ trợ reduced motion.
- Test hợp đồng nội dung, `py_compile` và Python test suite đều đạt.
- Trang được kiểm tra bằng trình duyệt ở desktop và mobile trước khi commit/push.

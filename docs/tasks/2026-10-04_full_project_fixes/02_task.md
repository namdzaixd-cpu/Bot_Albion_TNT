# Task list — F01–F36

User đã chốt implementation plan; phần mã nguồn và verification cô lập đã hoàn tất. Đánh dấu dưới đây chỉ là sửa/kiểm chứng trong repo, không đồng nghĩa production đã rollout. Mục tiêu tổng thể còn mở vì các điều kiện vận hành cuối trang chưa có bằng chứng.

| ID | Trạng thái mã | Kết quả/bằng chứng chính |
|---|---|---|
| F01 | [x] | Cold setup và chuỗi watchdog/repeated ready; một task, kill chỉ sau ngưỡng disconnect. |
| F02 | [x] | Restore party/view không clear ngay; startup rỗng vẫn khởi động lịch cleanup đủ tuần. |
| F03 | [x] | Claim/transition atomic; provider timeout giữ unknown; không resend mù; reconciliation có evidence. |
| F04 | [x] | Refund 100 từ snapshot sau đổi giá/xóa emoji; không refund theo giá mới hoặc Officer. |
| F05 | [x] | Attachment download thứ hai lỗi giữ message gốc. |
| F06 | [x] | Reload invalidate cache thật; lỗi giữ config đã tải thành công. |
| F07 | [x] | GET/PATCH CoreBank không trả raw token; omit token giữ secret. |
| F08 | [x] | Guild ID canonical; migrate legacy không đè row thật, không xóa nguồn. |
| F09 | [x] | Persist → authenticated reload; partial apply hiện lỗi, UI giữ state đã lưu và refresh overview. |
| F10 | [x] | Heartbeat dùng readiness hiện tại; not-ready không báo online. |
| F11 | [x] | Badge đọc main_bot; HTTP500 là unknown, không offline giả. |
| F12 | [x] source; [ ] rotate | Helper dùng env và log redacted; thiếu URL thất bại trước connect. Credential cũ chưa được chứng minh đã thu hồi. |
| F13 | [x] | Apply/reapply schema nguyên statement; lỗi cuối migration rollback toàn bộ. |
| F14 | [x] | Guild/actor từ server/session; FK thật và permission guards. |
| F15 | [x] | Homepage login tải blacklist same-origin; logout xóa dữ liệu cũ. |
| F16 | [x] | Metrics đúng system_logs/user_economy/ledger; DB lỗi trả 500, không empty success. |
| F17 | [x] | Runtime async/to_thread; no constructor I/O; ticker/ACK vẫn tiến trong I/O chậm. |
| F18 | [x] | Snapshot source/cwd rõ; protected legacy directory bị từ chối trước write. |
| F19 | [x] | SP balance/history/watermark atomic; concurrent import/manual delta không mất điểm. |
| F20 | [x] | SELECT lỗi không thay state bằng empty/default; Massing/templates khóa overwrite; Core unavailable rồi recover. |
| F21 | [x] | Move vào slot đầy giữ slot/fills cũ và persisted state; vacancy retry chuyển đúng một lần. |
| F22 | [x] | Stable report marker; title/status changes không tạo report hoặc ping mới; concurrent form không duplicate. |
| F23 | [x] | Pending/approved/rejected views có state riêng cho từng message. |
| F24 | [x] | Cache miss fetch/unarchive/reuse mapped thread; concurrent request chỉ create một thread. |
| F25 | [x] | Watermark là max timestamp hợp lệ; invalid amount không đẩy mốc; replay không cộng lại. |
| F26 | [x] | Dotenv/network guard trước import; default helper diagnostic offline; suite không dùng keys thật. |
| F27 | [x] | Component/custom ID/label boundary trước state publish; invalid form không tạo orphan. |
| F28 | [x] | Empty/legacy/reapply PostgreSQL; đủ bảng/RPC/FK/hardening, không overwrite vận hành. |
| F29 | [x] | Instruction path thật explicit; missing file fail trước provider/menu. |
| F30 | [x] | Public inventory đồng bộ; xóa source-text/wording/count/default-only tests, không re-pin. |
| F31 | [x] | Partial RPC/per-key emoji writes; concurrent edits giữ fields/token; UI autosave serialized, Toaster hiển thị lỗi. |
| F32 | [x] | Failed flush giữ dirty; retry không cần message mới; revised data không bị clear nhầm. |
| F33 | [x] | 2000/2005/2010/2015/2024 format đúng trong runtime nickname path. |
| F34 | [x] | Source-channel queue/session; move A→B không đọc backlog A trong B. |
| F35 | [x] code; [ ] production | Flask missing/wrong secret không dispatch; valid header dispatch; hai server callers gửi bearer secret. Cần xác nhận deployments/receiver thật. |
| F36 | [x] | ACK trước read/write/download hoặc đợi lock; runtime I/O >3s không trễ initial response. |

## Verification hoàn tất

- [x] Compile 41 Python files của đợt sửa; compile lại hai files sau thay đổi Core config unavailable/recovery.
- [x] Pytest toàn suite: **61 passed in 1.28s**.
- [x] Next.js production build và TypeScript phase thành công với source cuối, synthetic environment.
- [x] PostgreSQL disposable: empty/legacy/reapply, concurrency, rollback, permissions và provider-boundary financial runtime.
- [x] API handlers thật với fake integration boundaries; browser actual UI và screenshots.
- [x] README, architecture/storage/deployment/helper/feature docs và changelog cập nhật.

## Vận hành chưa có bằng chứng — giữ mục tiêu mở

- [ ] Rotate credential DB từng xuất hiện trong source, cập nhật secret hợp lệ và xác nhận credential cũ không còn hiệu lực bằng quyền provider.
- [ ] Backup/rollout DDL có kiểm soát trên production; không chạy operational snapshot như migration.
- [ ] Cấu hình WEBHOOK_SECRET/canonical guild trên deployments liên quan; xác nhận receiver của repo Chatbot riêng tương thích.
- [ ] Deploy bot/dashboard/chatbot cần thiết; kiểm tra production logs, readiness/health và reload listeners.
- [ ] Đối soát từng payment/refund unknown hoặc legacy bằng statement/reference thật trước khi cho phép retry/refund.

Không push/deploy, không sửa `.env` hoặc dữ liệu production và không chạy Discord bot thật trong đợt verification này. Chi tiết ở [03_walkthrough.md](03_walkthrough.md).

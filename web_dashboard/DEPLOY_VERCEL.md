# Hướng dẫn deploy Dashboard lên Vercel

Kiến trúc cuối cùng:
```
Render   -> bot Python (discord.py, chạy 24/7 giữ gateway)
Vercel   -> dashboard Next.js (web_dashboard/)
Supabase -> database dùng chung cho cả 2
```
Bot KHÔNG deploy lên Vercel được (serverless không giữ được websocket gateway).

---

## ⚠️ BẢO MẬT — đã vá, nhưng PHẢI set đúng env

Toàn bộ API dùng `SUPABASE_SERVICE_ROLE_KEY` (bypass RLS). Đã thêm:
- `src/middleware.ts` — chốt chặn tập trung cho mọi `/api/*`
- Guard lớp 2 trong từng route ghi
- Chặn UI `/dashboard` khi chưa đăng nhập

**BẮT BUỘC set `ADMIN_DISCORD_IDS` trên Vercel.** Cơ chế fail-closed: nếu
biến này trống thì KHÔNG AI sửa được dữ liệu (kể cả bro). Đây là cố ý, để
lúc quên set env thì hệ thống khoá lại thay vì mở toang.

Lấy Discord user ID: bật Developer Mode trong Discord (Settings → Advanced),
chuột phải vào tên mình → Copy User ID.

---

## 1. Chuẩn bị Discord OAuth

1. Vào https://discord.com/developers/applications -> chọn app của bot.
2. Tab **OAuth2** -> copy **Client ID** và **Client Secret** (bấm Reset nếu chưa có).
3. Mục **Redirects**, bấm Add và thêm ĐỦ 2 dòng:
   ```
   http://localhost:3000/api/auth/callback/discord
   https://<ten-project>.vercel.app/api/auth/callback/discord
   ```
   (dòng thứ 2 điền sau khi Vercel cấp domain ở bước 3, nhớ quay lại thêm)
4. Bấm **Save Changes**.

Điền 2 giá trị vừa lấy vào `web_dashboard/.env.local` để test local trước:
```
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
```

## 2. Push code lên GitHub

```bash
cd E:/AntiGravity/Bot_Albion_TNC
git add web_dashboard
git commit -m "thêm(dashboard): hướng dẫn deploy vercel"
git push origin main
```
Kiểm tra `.env.local` KHÔNG bị commit (đã có trong .gitignore, verify bằng
`git status --short`).

## 3. Tạo project trên Vercel

1. https://vercel.com -> đăng nhập bằng GitHub.
2. **Add New -> Project** -> import repo `namdzaixd-cpu/Bot_Albion_TNC`.
3. **QUAN TRỌNG — Root Directory:** bấm Edit, chọn **`web_dashboard`**.
   (Root repo là bot Python, để nguyên là build fail.)
4. Framework Preset: Next.js (tự nhận). Build/Output để mặc định.
5. Chưa bấm Deploy vội — thêm env ở bước 4 trước.

## 4. Environment Variables trên Vercel

Vào **Settings -> Environment Variables**, thêm từng biến (chọn cả 3 môi
trường Production / Preview / Development):

| Biến | Giá trị | Ghi chú |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | giống trong `.env` gốc của bot | công khai, ok |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | giống `.env` gốc | công khai, ok |
| `SUPABASE_SERVICE_ROLE_KEY` | giống `.env` gốc | **BÍ MẬT** - tuyệt đối không đổi tên thành NEXT_PUBLIC_ |
| `DISCORD_CLIENT_ID` | từ bước 1 | |
| `DISCORD_CLIENT_SECRET` | từ bước 1 | **BÍ MẬT** |
| `DISCORD_GUILD_ID` | giống `.env` gốc | |
| `NEXTAUTH_SECRET` | chuỗi ngẫu nhiên dài | tạo bằng `openssl rand -base64 32` |
| `NEXTAUTH_URL` | `https://<ten-project>.vercel.app` | **KHÔNG để localhost**, sai là login lỗi |
| `ADMIN_DISCORD_IDS` | `1064162008771084318` | **BẮT BUỘC** — ai được sửa data. Nhiều người ngăn bằng dấu phẩy |
| `BOT_WEBHOOK_URL` | `https://<bot-tren-render>.onrender.com/api/webhook/reload` | không phải 127.0.0.1 |
| `CHATBOT_WEBHOOK_URL` | `https://<chatbot-tren-render>.onrender.com/api/webhook/reload` | bot AI riêng |
| `NEXT_PUBLIC_API_URL` | `https://<ten-project>.vercel.app` | |

Bấm **Deploy**. Build xong Vercel cấp domain -> quay lại bước 1.3 thêm
redirect URI thật, và sửa lại `NEXTAUTH_URL` nếu lúc đầu đoán sai tên.

Sau khi sửa env phải **Redeploy** thì mới có hiệu lực.

## 5. Kiểm tra sau deploy

- [ ] Mở `https://<ten>.vercel.app` -> landing page hiện đủ 7 feature card
- [ ] Mở `/dashboard` -> sidebar 7 module hiện ra
- [ ] `curl https://<ten>.vercel.app/api/discord-data` -> trả JSON channels (Supabase ok)
- [ ] Bấm **Login** -> nhảy sang Discord -> quay về không lỗi `redirect_uri_mismatch`
- [ ] Xem tab **Logs** trên Vercel nếu có lỗi 500

Lỗi thường gặp:
- `redirect_uri_mismatch` -> redirect URI trong Discord Portal chưa khớp domain
- Login xong về localhost -> `NEXTAUTH_URL` sai
- API trả rỗng -> thiếu `SUPABASE_SERVICE_ROLE_KEY` trên Vercel
- Build fail ngay -> Root Directory chưa trỏ `web_dashboard`

## 6. Vá bảo mật (nên làm trước khi công khai URL)

Ý tưởng: chặn `PATCH /api/config` và trang `/dashboard` cho người lạ.

1. Tách config NextAuth ra file dùng chung, thêm callback lưu `token.sub`.
2. Trong `PATCH` của `src/app/api/config/route.ts`, gọi `getServerSession()`;
   nếu không có session hoặc `session.user.id` không nằm trong danh sách
   officer -> trả `401`.
3. Thêm biến env `ADMIN_DISCORD_IDS=id1,id2` để quy định ai được sửa.
4. Trong `src/app/dashboard/page.tsx`, nếu `useSession()` trả
   `status === "unauthenticated"` -> hiện nút đăng nhập thay vì form.

## 7. Giới hạn của Vercel free cần biết

- Serverless function timeout **10s** (dashboard chỉ đọc/ghi Supabase nên đủ).
- Không chạy được process nền / websocket -> bot vẫn phải ở Render.
- Free tier không bị sleep (khác Render free) -> không cần UptimeRobot.
- Mỗi `git push` lên `main` là Vercel tự deploy lại.

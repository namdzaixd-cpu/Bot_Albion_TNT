import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

/**
 * ─────────────────────────────────────────────────────────────────────────
 * CHỐT CHẶN BẢO MẬT TẬP TRUNG
 * ─────────────────────────────────────────────────────────────────────────
 * Middleware chạy TRƯỚC mọi API route, nên không thể quên bảo vệ route mới:
 * thêm file route.ts nào cũng tự động bị bao phủ.
 *
 * Nguyên tắc:
 *   - GET  (chỉ đọc)                -> cho phép, nhưng bắt buộc ĐĂNG NHẬP
 *   - POST/PATCH/PUT/DELETE (ghi)   -> bắt buộc ĐĂNG NHẬP + là ADMIN
 *   - /api/auth/*                   -> bỏ qua (chính là luồng đăng nhập)
 *
 * Lý do phải chặn: các API dùng SUPABASE_SERVICE_ROLE_KEY (bypass toàn bộ
 * RLS của Supabase). Không chặn = ai biết URL cũng đọc/xoá được dữ liệu guild.
 */

// Danh sách admin đọc từ env, so khớp bằng Discord user id.
// FAIL-CLOSED: env trống -> không ai là admin -> mọi thao tác ghi bị chặn.
function isAdminId(userId?: string | null): boolean {
  if (!userId) return false;
  const admins = (process.env.ADMIN_DISCORD_IDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return admins.length > 0 && admins.includes(userId);
}

const WRITE_METHODS = new Set(["POST", "PATCH", "PUT", "DELETE"]);

export default async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Luồng NextAuth phải để đi qua, nếu không sẽ không đăng nhập được.
  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
  });

  // 1) Chưa đăng nhập -> chặn hết
  if (!token) {
    return NextResponse.json(
      { error: "Chưa đăng nhập" },
      { status: 401 }
    );
  }

  // 2) Thao tác ghi -> phải là admin
  if (WRITE_METHODS.has(req.method) && !isAdminId(token.sub)) {
    return NextResponse.json(
      { error: "Không có quyền: chỉ officer/admin mới được sửa dữ liệu bot" },
      { status: 403 }
    );
  }

  return NextResponse.next();
}

export const config = {
  // Áp cho toàn bộ /api/* (trừ /api/auth đã lọc ở trên bằng code)
  matcher: ["/api/:path*"],
};

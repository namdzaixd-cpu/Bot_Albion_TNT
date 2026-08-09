import type { NextAuthOptions } from "next-auth";
import DiscordProvider from "next-auth/providers/discord";

/**
 * Cấu hình NextAuth dùng chung.
 * Tách ra file riêng để API route (server-side) cũng import được và gọi
 * getServerSession() kiểm tra đăng nhập.
 */
export const authOptions: NextAuthOptions = {
  providers: [
    DiscordProvider({
      clientId: process.env.DISCORD_CLIENT_ID || "",
      clientSecret: process.env.DISCORD_CLIENT_SECRET || "",
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 8, // phiên hết hạn sau 8 tiếng
  },
  callbacks: {
    async session({ session, token }) {
      if (session?.user) {
        // Gắn Discord user id + cờ admin vào session để UI dùng
        const u = session.user as { id?: string; isAdmin?: boolean };
        u.id = token.sub;
        u.isAdmin = isAdmin(token.sub);
      }
      return session;
    },
  },
};

/**
 * Danh sách Discord user ID được phép sửa cấu hình bot.
 * Khai báo trong env: ADMIN_DISCORD_IDS=123456,789012
 */
export function getAdminIds(): string[] {
  return (process.env.ADMIN_DISCORD_IDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Kiểm tra 1 Discord user id có quyền admin không.
 *
 * FAIL-CLOSED: nếu ADMIN_DISCORD_IDS chưa khai báo -> KHÔNG cho ai sửa.
 * Cố ý làm vậy để lúc deploy quên set env thì hệ thống khoá lại,
 * chứ không phải mở toang cho mọi người đăng nhập đều sửa được bot.
 */
export function isAdmin(userId?: string | null): boolean {
  if (!userId) return false;
  const admins = getAdminIds();
  if (admins.length === 0) return false;
  return admins.includes(userId);
}

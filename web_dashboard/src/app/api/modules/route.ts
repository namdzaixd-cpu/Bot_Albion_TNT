import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { supabase } from "@/lib/supabaseServer";
import { authOptions, isAdmin } from "@/lib/auth";

const GUILD_ID = process.env.DISCORD_GUILD_ID || process.env.GUILD_ID || "default";

/**
 * Bật/tắt TOÀN BỘ module cùng lúc (công tắc tổng).
 *
 * Body: { enabled: boolean }
 *
 * Chỉ đụng vào những cột dạng is_<ten>_enabled đang có thật trong bảng
 * config, nên không bao giờ ghi nhầm sang cột khác.
 */
export async function PATCH(request: Request) {
  // ── Lớp bảo vệ 2 (proxy.ts đã chặn ở vòng ngoài) ───────────────────
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }
  if (!isAdmin((session.user as { id?: string }).id)) {
    return NextResponse.json(
      { error: "Bạn không có quyền quản trị" },
      { status: 403 }
    );
  }

  try {
    const body = await request.json();
    if (typeof body?.enabled !== "boolean") {
      return NextResponse.json(
        { error: "Thiếu trường 'enabled' (true/false)" },
        { status: 400 }
      );
    }
    const enabled: boolean = body.enabled;

    // Đọc hàng config hiện tại để biết CÓ những cột nào
    const { data: row, error: readErr } = await supabase
      .from("guild_config")
      .select("*")
      .eq("guild_id", GUILD_ID)
      .maybeSingle();

    if (readErr) throw readErr;
    if (!row) {
      return NextResponse.json(
        { error: "Chưa có cấu hình cho guild này" },
        { status: 404 }
      );
    }

    const keys = Object.keys(row).filter((k) => /^is_.+_enabled$/.test(k));
    if (keys.length === 0) {
      return NextResponse.json(
        { error: "Không tìm thấy module nào để bật/tắt" },
        { status: 404 }
      );
    }

    const patch: Record<string, boolean> = {};
    for (const k of keys) patch[k] = enabled;

    const { error: upErr } = await supabase
      .from("guild_config")
      .update(patch)
      .eq("guild_id", GUILD_ID);

    if (upErr) throw upErr;

    return NextResponse.json({
      success: true,
      enabled,
      updated: keys,
      count: keys.length,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Lỗi không xác định";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

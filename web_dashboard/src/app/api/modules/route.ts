import { NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { supabase } from "@/lib/supabaseServer";
import { authOptions, isAdmin } from "@/lib/auth";
import { GUILD_ID } from "@/lib/guild";
import { reloadBots } from "@/lib/reloadBots";

/**
 * Bật/tắt TOÀN BỘ module cùng lúc (công tắc tổng).
 *
 * Body: { enabled: boolean }
 *
 * Chỉ đụng vào những cột dạng is_<ten>_enabled đang có thật trong bảng
 * config, nên không bao giờ ghi nhầm sang cột khác.
 */
export async function PATCH(request: Request) {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }
  const user = session.user as { id?: string };
  if (!isAdmin(user.id)) {
    return NextResponse.json(
      { error: "Bạn không có quyền quản trị" },
      { status: 403 }
    );
  }

  try {
    const body: unknown = await request.json();
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return NextResponse.json(
        { error: "Thiếu trường 'enabled' (true/false)" },
        { status: 400 }
      );
    }
    const enabled = Reflect.get(body, 'enabled');
    if (typeof enabled !== 'boolean') {
      return NextResponse.json(
        { error: "Thiếu trường 'enabled' (true/false)" },
        { status: 400 }
      );
    }

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

    const keys = Object.keys(row).filter((key) => /^is_.+_enabled$/.test(key));
    if (keys.length === 0) {
      return NextResponse.json(
        { error: "Không tìm thấy module nào để bật/tắt" },
        { status: 404 }
      );
    }

    const patch: Record<string, boolean> = {};
    for (const key of keys) patch[key] = enabled;

    const { data: updatedRow, error: updateError } = await supabase
      .from("guild_config")
      .update(patch)
      .eq("guild_id", GUILD_ID)
      .select("guild_id")
      .maybeSingle();
    if (updateError) throw updateError;
    if (!updatedRow) {
      return NextResponse.json(
        { error: "Không thể xác nhận cấu hình guild đã được lưu." },
        { status: 404 }
      );
    }
    const result = {
      success: true,
      enabled,
      updated: keys,
      count: keys.length,
    };
    const reload = await reloadBots();
    if (!reload.ok) {
      return NextResponse.json(
        { ...result, saved: true, applied: false, error: reload.error },
        { status: 502 }
      );
    }
    return NextResponse.json({ ...result, saved: true, applied: true });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Lỗi không xác định";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

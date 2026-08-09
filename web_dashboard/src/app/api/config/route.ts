import { NextResponse } from 'next/server';
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";

// Lấy GUILD_ID từ môi trường
const GUILD_ID = process.env.DISCORD_GUILD_ID || "712258265769050164";

export async function GET() {
  try {
    const { data, error } = await supabase
      .from('guild_config')
      .select('*')
      .eq('guild_id', GUILD_ID)
      .single();

    if (error) {
      if (error.code === 'PGRST116') {
        // Không tìm thấy bản ghi, có thể bot chưa tạo
        return NextResponse.json({ 
          guild_id: GUILD_ID,
          is_onboard_enabled: false 
        });
      }
      throw error;
    }

    return NextResponse.json(data);
  } catch (error: any) {
    console.error("Lỗi khi gọi API /api/config:", error.message);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
  try {
    // ── Lớp bảo vệ 2 (middleware là lớp 1) ────────────────────────────
    // Không tin tưởng mỗi middleware: nếu matcher bị sửa nhầm thì route
    // vẫn tự chặn được. API này bypass RLS nên phải chắc chắn.
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
    }
    if (!isAdmin((session.user as { id?: string }).id)) {
      return NextResponse.json(
        { error: "Không có quyền sửa dữ liệu bot" },
        { status: 403 }
      );
    }
    // ──────────────────────────────────────────────────────────────────
    const body = await request.json();
    const { is_onboard_enabled, ...otherUpdates } = body;

    const updateData: any = {};
    if (is_onboard_enabled !== undefined) {
      updateData.is_onboard_enabled = is_onboard_enabled;
    }
    
    for (const key of Object.keys(otherUpdates)) {
        updateData[key] = otherUpdates[key];
    }

    const { data, error } = await supabase
      .from('guild_config')
      .update(updateData)
      .eq('guild_id', GUILD_ID)
      .select()
      .single();

    if (error) throw error;

    // Trigger webhook để bot discord load lại config
    if (process.env.BOT_WEBHOOK_URL) {
      try {
        fetch(process.env.BOT_WEBHOOK_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }).catch(e => console.error("Không thể trigger webhook:", e));
      } catch (e) {
        console.error("Lỗi khi gửi webhook:", e);
      }
    }

    return NextResponse.json(data);
  } catch (error: any) {
    console.error("Lỗi cập nhật config:", error.message);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

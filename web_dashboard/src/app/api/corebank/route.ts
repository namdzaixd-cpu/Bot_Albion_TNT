import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";

const GUILD_ID = process.env.GUILD_ID || "default";

export async function GET() {
  try {
    const { data, error } = await supabase
      .from("corebank_config")
      .select("*")
      .eq("guild_id", GUILD_ID)
      .single();

    if (error && error.code !== "PGRST116") {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Nếu chưa có, trả về mặc định
    return NextResponse.json(data || {
      core_channel_id: "",
      bank_channel_id: "",
      unbelievaboat_token: "",
      emoji_map: {},
      auto_react: true
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
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
    const body = await req.json();

    const { data, error } = await supabase
      .from("corebank_config")
      .upsert({ guild_id: GUILD_ID, ...body })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    
    // Gửi webhook để cả 2 Bot reload config
    for (const webhookUrl of [process.env.BOT_WEBHOOK_URL, process.env.CHATBOT_WEBHOOK_URL]) {
      if (webhookUrl) {
        try {
          fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: "config_reload" }),
          }).catch(e => console.error("Lỗi gọi webhook:", e));
        } catch (e) {
          console.error("Lỗi gọi webhook:", e);
        }
      }
    }

    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

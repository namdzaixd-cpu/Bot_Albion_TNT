import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";

const GUILD_ID = process.env.DISCORD_GUILD_ID || process.env.GUILD_ID || "default";

/**
 * Lấy số thành viên THẬT của guild Discord.
 * Dùng endpoint /guilds/{id}?with_counts=true -> approximate_member_count.
 * Trả null nếu không có token hoặc gọi lỗi, để UI biết mà hiện "—"
 * thay vì bịa ra một con số.
 */
async function fetchMemberCount(): Promise<number | null> {
  const token = process.env.DISCORD_TOKEN;
  if (!token || !GUILD_ID || GUILD_ID === "default") return null;
  try {
    const res = await fetch(
      `https://discord.com/api/v10/guilds/${GUILD_ID}?with_counts=true`,
      {
        headers: {
          Authorization: `Bot ${token}`,
          // Discord BẮT BUỘC User-Agent cho request từ server,
          // thiếu là bị chặn 403 dù token hoàn toàn hợp lệ.
          "User-Agent": "DiscordBot (https://bot-albion-tnt.vercel.app, 1.0)",
        },
        next: { revalidate: 60 }, // cache 60s, tránh dính rate limit
      }
    );
    if (!res.ok) return null;
    const g = await res.json();
    return (
      g.approximate_member_count ?? g.member_count ?? null
    );
  } catch {
    return null;
  }
}

export async function GET() {
  try {
    // Song song lấy dữ liệu từ các bảng + Discord API
    const [corebank, blacklist, logs, siphoned, cfg, memberCount] =
      await Promise.all([
        supabase.from("corebank_config").select("*").eq("guild_id", GUILD_ID).maybeSingle(),
        supabase.from("blacklist").select("id", { count: "exact" }).eq("guild_id", GUILD_ID),
        supabase.from("logs").select("*").order("created_at", { ascending: false }).limit(8),
        supabase.from("siphoned_energy").select("*", { count: "exact" }).eq("guild_id", GUILD_ID),
        supabase.from("guild_config").select("*").eq("guild_id", GUILD_ID).maybeSingle(),
        fetchMemberCount(),
      ]);

    // ── Danh sách module bật/tắt ──────────────────────────────────────
    // Tự dò các cột dạng is_<ten>_enabled đang CÓ THẬT trong bảng config,
    // nên thêm cột mới trong Supabase là dashboard tự hiện, không cần sửa code.
    const row = (cfg.data || {}) as Record<string, unknown>;
    const modules = Object.keys(row)
      .filter((k) => /^is_.+_enabled$/.test(k))
      .sort()
      .map((key) => ({
        key,
        id: key.replace(/^is_/, "").replace(/_enabled$/, ""),
        enabled: Boolean(row[key]),
      }));

    const stats = {
      members: memberCount,            // null = không lấy được, UI hiện "—"
      members_live: memberCount !== null,
      corebank_total: corebank.data?.total_silver ?? 0,
      blacklist_count: blacklist.count ?? 0,
      ai_today: logs.data?.filter((l: { type?: string }) => l.type === "ai").length ?? 0,
    };

    const activity = (logs.data || []).map(
      (l: Record<string, string>) => ({
        time: l.created_at,
        event: l.message || l.event || "—",
        module: l.module || l.type || "system",
        status: l.status || "ok",
      })
    );

    return new NextResponse(
      JSON.stringify({
        stats,
        modules,
        activity,
        siphoned_count: siphoned.count ?? 0,
        updated_at: new Date().toISOString(),
      }),
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Lỗi không xác định";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

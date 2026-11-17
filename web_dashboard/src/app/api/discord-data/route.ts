import { NextResponse } from 'next/server';
import { supabase } from "@/lib/supabaseServer";

const GUILD_ID = process.env.DISCORD_GUILD_ID || "712258265769050164";

export async function GET() {
  try {
    const [channelsRes, rolesRes] = await Promise.all([
      supabase.from('discord_channels').select('*').eq('guild_id', GUILD_ID),
      supabase.from('discord_roles').select('*').eq('guild_id', GUILD_ID)
    ]);

    if (channelsRes.error) throw channelsRes.error;
    if (rolesRes.error) throw rolesRes.error;

    // Filter text channels or category for relevant things (optional), but we just return all for now
    return NextResponse.json({
      channels: channelsRes.data || [],
      roles: rolesRes.data || []
    });
  } catch (error: any) {
    console.error("Lỗi lấy discord data:", error.message);
    return NextResponse.json({ error: "Không thể tải dữ liệu Discord." }, { status: 500 });
  }
}

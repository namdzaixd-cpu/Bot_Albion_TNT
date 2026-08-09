import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";

// Bot ghi heartbeat vào json_storage (file_name = tnc_bot_status.json)
// mỗi 60s. Web đọc ở đây để hiện trạng thái online thực tế.
const KEY = "tnc_bot_status.json";

export async function GET() {
  try {
    const { data, error } = await supabase
      .from("json_storage")
      .select("data")
      .eq("file_name", KEY)
      .maybeSingle();
    if (error) throw error;

    const payload = (data?.data ?? {}) as {
      online?: boolean; last_seen?: string; latency_ms?: number | null;
    };
    const last = payload.last_seen ? new Date(payload.last_seen).getTime() : 0;
    const online = !!payload.online && Date.now() - last < 90_000;

    return new NextResponse(
      JSON.stringify({
        online,
        last_seen: payload.last_seen ?? null,
        latency_ms: payload.latency_ms ?? null,
      }),
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Lỗi";
    return NextResponse.json({ error: msg, online: false }, { status: 500 });
  }
}

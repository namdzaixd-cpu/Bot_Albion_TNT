import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";

// Bot ghi heartbeat vào json_storage mỗi 60s.
// Main bot: tnc_bot_status.json | Chatbot: tnc_chatbot_status.json
const MAIN_KEY = "tnc_bot_status.json";
const CHATBOT_KEY = "tnc_chatbot_status.json";

async function fetchStatus(key: string) {
  const { data, error } = await supabase
    .from("json_storage")
    .select("data")
    .eq("file_name", key)
    .maybeSingle();
  if (error) throw error;

  const payload = (data?.data ?? {}) as {
    online?: boolean; last_seen?: string; latency_ms?: number | null;
  };
  const last = payload.last_seen ? new Date(payload.last_seen).getTime() : 0;
  const online = !!payload.online && Date.now() - last < 90_000;

  return {
    online,
    last_seen: payload.last_seen ?? null,
    latency_ms: payload.latency_ms ?? null,
  };
}

export async function GET() {
  try {
    const [mainBot, chatbot] = await Promise.all([
      fetchStatus(MAIN_KEY),
      fetchStatus(CHATBOT_KEY),
    ]);

    return new NextResponse(
      JSON.stringify({ main_bot: mainBot, chatbot }),
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Lỗi";
    return NextResponse.json(
      { error: msg, main_bot: { online: false }, chatbot: { online: false } },
      { status: 500 }
    );
  }
}

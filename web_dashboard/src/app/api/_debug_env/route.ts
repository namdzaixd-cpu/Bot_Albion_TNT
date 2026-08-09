import { NextResponse } from "next/server";

// TEMP DEBUG — xoá sau khi verify xong. Không lộ secret, chỉ in metadata.
export async function GET() {
  const check = (k: string) => {
    const v = process.env[k] || "";
    return { set: v.length > 0, len: v.length, preview: v.slice(0, 6) + (v.length > 6 ? "..." : "") };
  };
  const envs = [
    "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DISCORD_GUILD_ID",
    "DISCORD_TOKEN", "NEXTAUTH_SECRET", "ADMIN_DISCORD_IDS", "NEXT_PUBLIC_API_URL",
  ].map((k) => ({ key: k, ...check(k) }));
  return NextResponse.json({ envs, now: new Date().toISOString() });
}

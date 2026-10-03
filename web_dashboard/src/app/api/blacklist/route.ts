import { NextResponse } from "next/server";
import type { Session } from "next-auth";
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";
import { GUILD_ID } from "@/lib/guild";

function authorizeAdmin(session: Session | null) {
  if (!session?.user) {
    return { error: NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 }) };
  }
  const user = session.user as { id?: string };
  if (!user.id || !isAdmin(user.id)) {
    return { error: NextResponse.json({ error: "Không có quyền sửa dữ liệu bot" }, { status: 403 }) };
  }
  return { actorId: user.id };
}

export async function GET() {
  try {
    const { data, error } = await supabase
      .from("blacklist")
      .select("*")
      .order("timestamp", { ascending: false });

    if (error) {
      return NextResponse.json({ error: "Không thể tải blacklist." }, { status: 500 });
    }
    return NextResponse.json(data || []);
  } catch {
    return NextResponse.json({ error: "Không thể tải blacklist." }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const authorization = authorizeAdmin(await getServerSession(authOptions));
    if ('error' in authorization) return authorization.error;

    const body: unknown = await request.json();
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return NextResponse.json({ error: 'Nội dung blacklist không hợp lệ.' }, { status: 400 });
    }
    const discordId = Reflect.get(body, 'discord_id');
    const ingameName = Reflect.get(body, 'ingame_name');
    const reason = Reflect.get(body, 'reason');
    if (
      typeof discordId !== 'string' || !discordId ||
      typeof ingameName !== 'string' || !ingameName ||
      typeof reason !== 'string' || !reason
    ) {
      return NextResponse.json({ error: 'Thiếu thông tin blacklist hợp lệ.' }, { status: 400 });
    }
    const suppliedIngameId = Reflect.get(body, 'ingame_id');
    if (suppliedIngameId !== undefined && typeof suppliedIngameId !== 'string') {
      return NextResponse.json({ error: 'Ingame ID không hợp lệ.' }, { status: 400 });
    }

    const { data, error } = await supabase
      .from("blacklist")
      .upsert({
        discord_id: discordId,
        ingame_name: ingameName,
        ingame_id: suppliedIngameId ?? "N/A (Added via Web)",
        reason,
        added_by_discord_id: authorization.actorId,
        source_guild_id: GUILD_ID,
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: "Không thể lưu blacklist." }, { status: 500 });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Không thể xử lý blacklist." }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const authorization = authorizeAdmin(await getServerSession(authOptions));
    if ('error' in authorization) return authorization.error;

    const url = new URL(request.url);
    const discordId = url.searchParams.get("discord_id");
    if (!discordId) {
      return NextResponse.json({ error: "Thiếu discord_id" }, { status: 400 });
    }

    const { error } = await supabase
      .from("blacklist")
      .delete()
      .eq("discord_id", discordId);

    if (error) {
      return NextResponse.json({ error: "Không thể xóa khỏi blacklist." }, { status: 500 });
    }
    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json({ error: "Không thể xử lý blacklist." }, { status: 500 });
  }
}

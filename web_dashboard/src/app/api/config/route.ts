import { NextResponse } from 'next/server';
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";
import { GUILD_ID } from "@/lib/guild";
import { reloadBots } from "@/lib/reloadBots";

const WRITABLE_FIELDS = [
  'is_onboard_enabled',
  'apply_channel_id',
  'question_channel_id',
  'rules_channel_id',
  'chat_channel_id',
  'officer_role_id',
  'member_role_id',
] as const;

export async function GET() {
  try {
    const { data, error } = await supabase
      .from('guild_config')
      .select('*')
      .eq('guild_id', GUILD_ID)
      .single();

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ guild_id: GUILD_ID, is_onboard_enabled: false });
      }
      throw error;
    }

    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Lỗi không xác định';
    console.error("Lỗi khi gọi API /api/config:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) {
      return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
    }
    const user = session.user as { id?: string };
    if (!isAdmin(user.id)) {
      return NextResponse.json(
        { error: "Không có quyền sửa dữ liệu bot" },
        { status: 403 }
      );
    }

    const body: unknown = await request.json();
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return NextResponse.json({ error: 'Nội dung cập nhật không hợp lệ.' }, { status: 400 });
    }

    const updates: Record<string, boolean | string> = {};
    for (const field of WRITABLE_FIELDS) {
      if (!(field in body)) continue;
      const value = Reflect.get(body, field);
      if (field === 'is_onboard_enabled') {
        if (typeof value !== 'boolean') {
          return NextResponse.json({ error: 'Trường cấu hình không hợp lệ.' }, { status: 400 });
        }
        updates[field] = value;
      } else {
        if (typeof value !== 'string') {
          return NextResponse.json({ error: 'Trường cấu hình không hợp lệ.' }, { status: 400 });
        }
        updates[field] = value;
      }
    }
    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ error: 'Không có trường cấu hình hợp lệ.' }, { status: 400 });
    }

    const { data, error } = await supabase
      .from('guild_config')
      .update(updates)
      .eq('guild_id', GUILD_ID)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: 'Không thể lưu cấu hình guild.' }, { status: 500 });
    }

    const reload = await reloadBots();
    if (!reload.ok) {
      return NextResponse.json(
        { ...data, saved: true, applied: false, error: reload.error },
        { status: 502 }
      );
    }
    return NextResponse.json({ ...data, saved: true, applied: true });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Lỗi không xác định';
    console.error("Lỗi cập nhật config:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

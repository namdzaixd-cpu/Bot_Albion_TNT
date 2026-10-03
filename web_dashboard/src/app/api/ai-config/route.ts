import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { supabase } from "@/lib/supabaseServer";
import { authOptions, isAdmin } from "@/lib/auth";
import { GUILD_ID } from "@/lib/guild";
import { reloadBots } from "@/lib/reloadBots";

const DEFAULT_CONFIG = {
  guild_id: GUILD_ID,
  channel_buffers: {},
  intercept_channels: [],
  autowiki_channels: [],
  library_channel_ids: [],
  vision_channels: [],
  model: 'inclusionai/ling-3.0-flash:free',
};

const WRITABLE_FIELDS = [
  'model',
  'intercept_channels',
  'autowiki_channels',
  'library_channel_ids',
  'vision_channels',
] as const;

export async function GET() {
  try {
    const { data, error } = await supabase.rpc('dashboard_get_ai_config', {
      p_guild_id: GUILD_ID,
    });
    if (error) {
      return NextResponse.json({ error: 'Không thể tải cấu hình AI.' }, { status: 500 });
    }
    return NextResponse.json(data ?? DEFAULT_CONFIG);
  } catch {
    return NextResponse.json({ error: 'Không thể tải cấu hình AI.' }, { status: 500 });
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

    const patch: Record<string, string | string[]> = {};
    for (const field of WRITABLE_FIELDS) {
      if (!(field in body)) continue;
      const value = Reflect.get(body, field);
      if (field === 'model') {
        if (typeof value !== 'string') {
          return NextResponse.json({ error: 'Trường cấu hình AI không hợp lệ.' }, { status: 400 });
        }
        patch[field] = value;
        continue;
      }
      if (!Array.isArray(value)) {
        return NextResponse.json({ error: 'Trường cấu hình AI không hợp lệ.' }, { status: 400 });
      }
      const channelIds = value.filter((item: unknown): item is string => typeof item === 'string');
      if (channelIds.length !== value.length) {
        return NextResponse.json({ error: 'Trường cấu hình AI không hợp lệ.' }, { status: 400 });
      }
      patch[field] = channelIds;
    }
    if (Object.keys(patch).length === 0) {
      return NextResponse.json({ error: 'Không có trường cấu hình AI hợp lệ.' }, { status: 400 });
    }

    const { data, error } = await supabase.rpc('dashboard_patch_ai_config', {
      p_guild_id: GUILD_ID,
      p_patch: patch,
    });
    if (error) {
      return NextResponse.json({ error: 'Không thể lưu cấu hình AI.' }, { status: 500 });
    }

    const reload = await reloadBots();
    if (!reload.ok) {
      return NextResponse.json(
        { success: true, data, saved: true, applied: false, error: reload.error },
        { status: 502 }
      );
    }
    return NextResponse.json({ success: true, data, saved: true, applied: true });
  } catch {
    return NextResponse.json({ error: 'Không thể xử lý cập nhật AI.' }, { status: 500 });
  }
}

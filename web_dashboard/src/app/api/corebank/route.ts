import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";
import { GUILD_ID } from "@/lib/guild";
import { reloadBots } from "@/lib/reloadBots";

function publicConfig(value: unknown) {
  const row = value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  const rawEmojiMap = row ? Reflect.get(row, 'emoji_map') : null;
  const emojiMap: Record<string, { name: string; value: number; display: string; order: number }> = {};
  if (rawEmojiMap && typeof rawEmojiMap === 'object' && !Array.isArray(rawEmojiMap)) {
    for (const [key, rawEmoji] of Object.entries(rawEmojiMap)) {
      if (!rawEmoji || typeof rawEmoji !== 'object' || Array.isArray(rawEmoji)) continue;
      const name = Reflect.get(rawEmoji, 'name');
      const amount = Reflect.get(rawEmoji, 'value');
      if (typeof name !== 'string' || typeof amount !== 'number' || !Number.isFinite(amount)) continue;
      const display = Reflect.get(rawEmoji, 'display');
      const order = Reflect.get(rawEmoji, 'order');
      emojiMap[key] = {
        name,
        value: amount,
        display: typeof display === 'string' ? display : key,
        order: typeof order === 'number' && Number.isFinite(order) ? order : 0,
      };
    }
  }

  const token = row ? Reflect.get(row, 'unbelievaboat_token') : null;
  const coreChannel = row ? Reflect.get(row, 'core_channel_id') : null;
  const bankChannel = row ? Reflect.get(row, 'bank_channel_id') : null;
  const autoReact = row ? Reflect.get(row, 'auto_react') : null;
  return {
    guild_id: GUILD_ID,
    core_channel_id: typeof coreChannel === 'string' ? coreChannel : '',
    bank_channel_id: typeof bankChannel === 'string' ? bankChannel : '',
    token_configured: typeof token === 'string' && token.length > 0,
    emoji_map: emojiMap,
    auto_react: typeof autoReact === 'boolean' ? autoReact : true,
  };
}

function errorResponse(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}

export async function GET() {
  try {
    const { data, error } = await supabase.rpc("dashboard_get_corebank_config", {
      p_guild_id: GUILD_ID,
    });
    if (error) return errorResponse("Không thể tải cấu hình CoreBank.", 500);
    return NextResponse.json(publicConfig(data));
  } catch {
    return errorResponse("Không thể tải cấu hình CoreBank.", 500);
  }
}

export async function PATCH(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session?.user) return errorResponse("Chưa đăng nhập", 401);
    const user = session.user as { id?: string };
    if (!isAdmin(user.id)) return errorResponse("Không có quyền sửa dữ liệu bot", 403);

    const body: unknown = await req.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      return errorResponse("Nội dung cập nhật không hợp lệ.", 400);
    }

    let data: unknown = null;
    const emojiOperation = Reflect.get(body, 'emoji_operation');
    if (emojiOperation !== undefined) {
      const isRemove = emojiOperation === "remove";
      const isSet = emojiOperation === "set";
      const key = Reflect.get(body, 'key');
      const value = Reflect.get(body, 'value');
      if ((!isRemove && !isSet) || typeof key !== "string" || !key) {
        return errorResponse("Thao tác emoji không hợp lệ.", 400);
      }
      if (isSet && (
        !value || typeof value !== "object" || Array.isArray(value) ||
        typeof Reflect.get(value, 'name') !== "string" ||
        typeof Reflect.get(value, 'display') !== "string" ||
        typeof Reflect.get(value, 'value') !== "number" || !Number.isFinite(Reflect.get(value, 'value')) ||
        typeof Reflect.get(value, 'order') !== "number" || !Number.isFinite(Reflect.get(value, 'order'))
      )) {
        return errorResponse("Thông tin emoji không hợp lệ.", 400);
      }

      const result = await supabase.rpc("dashboard_mutate_corebank_emoji", {
        p_guild_id: GUILD_ID,
        p_key: key,
        p_value: isSet ? value : null,
        p_remove: isRemove,
      });
      if (result.error) return errorResponse("Không thể lưu emoji CoreBank.", 500);
      data = result.data;
    } else {
      const allowed = [
        "core_channel_id",
        "bank_channel_id",
        "unbelievaboat_token",
        "auto_react",
      ] as const;
      const patch: Record<string, string | boolean> = {};
      for (const key of allowed) {
        if (!(key in body)) continue;
        const value = Reflect.get(body, key);
        if (key === "auto_react") {
          if (typeof value !== "boolean") {
            return errorResponse("Trường cấu hình CoreBank không hợp lệ.", 400);
          }
          patch[key] = value;
        } else {
          if (typeof value !== "string") {
            return errorResponse("Trường cấu hình CoreBank không hợp lệ.", 400);
          }
          patch[key] = value;
        }
      }
      if (Object.keys(patch).length === 0) {
        return errorResponse("Không có trường cấu hình CoreBank hợp lệ.", 400);
      }

      const result = await supabase.rpc("dashboard_patch_corebank_config", {
        p_guild_id: GUILD_ID,
        p_patch: patch,
      });
      if (result.error) return errorResponse("Không thể lưu cấu hình CoreBank.", 500);
      data = result.data;
    }

    const config = publicConfig(data);
    const reload = await reloadBots();
    if (!reload.ok) {
      return NextResponse.json(
        { ...config, saved: true, applied: false, error: reload.error },
        { status: 502 }
      );
    }
    return NextResponse.json({ ...config, saved: true, applied: true });
  } catch {
    return errorResponse("Không thể xử lý cập nhật CoreBank.", 500);
  }
}

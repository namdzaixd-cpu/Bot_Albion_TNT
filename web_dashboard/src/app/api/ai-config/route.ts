import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { supabase } from "@/lib/supabaseServer";
import { authOptions, isAdmin } from "@/lib/auth";

export async function GET() {
  try {
    const { data, error } = await supabase
      .from('ai_config')
      .select('*')
      .eq('guild_id', 'default')
      .single();

    if (error && error.code !== 'PGRST116') { // PGRST116 is no rows returned
      console.error('Error fetching AI config:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    if (!data) {
      // Default initial config
      const defaultConfig = {
        guild_id: 'default',
        channel_buffers: {},
        intercept_channels: [],
        autowiki_channels: [],
        library_channel_ids: [],
        vision_channels: [],
        model: 'inclusionai/ling-3.0-flash:free'
      };
      return NextResponse.json(defaultConfig);
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error('Unexpected error:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
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
    const updateData = await request.json();

    // Ensure it belongs to default
    updateData.guild_id = 'default';

    const { data, error } = await supabase
      .from('ai_config')
      .upsert(updateData)
      .select()
      .single();

    if (error) {
      console.error('Error updating AI config:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Trigger webhook to the bot to reload config
    const webhookUrl = process.env.BOT_WEBHOOK_URL;
    if (webhookUrl) {
      try {
        await fetch(webhookUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ event: 'config_reload' })
        });
        console.log('Webhook triggered for AI config reload');
      } catch (webhookError) {
        console.error('Failed to trigger webhook:', webhookError);
        // We don't fail the request if webhook fails, just log it
      }
    }

    return NextResponse.json({ success: true, data });
  } catch (err) {
    console.error('Unexpected error:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

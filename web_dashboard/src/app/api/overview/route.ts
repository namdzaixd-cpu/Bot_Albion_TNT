import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { GUILD_ID } from "@/lib/guild";

async function fetchMemberCount(): Promise<number | null> {
  const token = process.env.DISCORD_TOKEN;
  if (!token) return null;
  try {
    const response = await fetch(
      `https://discord.com/api/v10/guilds/${GUILD_ID}?with_counts=true`,
      {
        headers: {
          Authorization: `Bot ${token}`,
          "User-Agent": "DiscordBot (https://bot-albion-tnt.vercel.app, 1.0)",
        },
        next: { revalidate: 60 },
      }
    );
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object') return null;
    const count = Reflect.get(payload, 'approximate_member_count') ?? Reflect.get(payload, 'member_count');
    return typeof count === 'number' && Number.isFinite(count) ? count : null;
  } catch {
    return null;
  }
}

export async function GET() {
  try {
    const [metricsResult, logsResult, configResult, memberCount] = await Promise.all([
      supabase.rpc('dashboard_overview_metrics', { p_guild_id: GUILD_ID }),
      supabase
        .from('system_logs')
        .select('id,level,module,message,created_at')
        .eq('guild_id', GUILD_ID)
        .order('created_at', { ascending: false })
        .limit(8),
      supabase.from('guild_config').select('*').eq('guild_id', GUILD_ID).maybeSingle(),
      fetchMemberCount(),
    ]);

    if (metricsResult.error || logsResult.error || configResult.error) {
      console.error('Lỗi truy vấn dữ liệu tổng quan:', {
        metrics: metricsResult.error?.message,
        logs: logsResult.error?.message,
        config: configResult.error?.message,
      });
      return NextResponse.json(
        { error: 'Không thể tải đầy đủ dữ liệu tổng quan. Vui lòng thử lại.' },
        { status: 500 }
      );
    }
    if (!metricsResult.data || typeof metricsResult.data !== 'object') {
      return NextResponse.json({ error: 'Dữ liệu tổng quan không hợp lệ.' }, { status: 500 });
    }

    const metric = metricsResult.data;
    const readCount = (field: string) => {
      const value = Reflect.get(metric, field);
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new Error(`Invalid overview metric: ${field}`);
      }
      return value;
    };

    const configData: unknown = configResult.data ?? {};
    const configEntries = configData && typeof configData === 'object'
      ? Object.entries(configData)
      : [];
    const modules = configEntries
      .filter(([key]) => /^is_.+_enabled$/.test(key))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        id: key.replace(/^is_/, '').replace(/_enabled$/, ''),
        enabled: value === true,
      }));

    const activity = (logsResult.data ?? []).map((log: {
      created_at: string; message: string | null; module: string | null; level: string;
    }) => ({
      time: log.created_at,
      event: log.message || '—',
      module: log.module || 'system',
      status: log.level === 'ERROR' ? 'error' : 'ok',
    }));

    return NextResponse.json(
      {
        stats: {
          members: memberCount,
          members_live: memberCount !== null,
          corebank_total: readCount('corebank_total'),
          blacklist_count: readCount('blacklist_count'),
          ai_today: readCount('ai_today'),
        },
        modules,
        activity,
        siphoned_count: readCount('siphoned_count'),
        updated_at: new Date().toISOString(),
      },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error: unknown) {
    console.error('Lỗi tổng quan dashboard:', error instanceof Error ? error.message : 'Lỗi không xác định');
    return NextResponse.json(
      { error: 'Không thể tải dữ liệu tổng quan. Vui lòng thử lại.' },
      { status: 500 }
    );
  }
}

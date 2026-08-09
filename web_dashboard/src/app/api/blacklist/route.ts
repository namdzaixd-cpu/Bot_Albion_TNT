import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";

export async function GET() {
  try {
    const { data, error } = await supabase
      .from("blacklist")
      .select("*")
      .order("timestamp", { ascending: false });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(data || []);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
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
    const body = await req.json();

    const { data, error } = await supabase
      .from("blacklist")
      .upsert(body)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
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
    const url = new URL(req.url);
    const discord_id = url.searchParams.get("discord_id");

    if (!discord_id) {
      return NextResponse.json({ error: "Thiếu discord_id" }, { status: 400 });
    }

    const { error } = await supabase
      .from("blacklist")
      .delete()
      .eq("discord_id", discord_id);

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

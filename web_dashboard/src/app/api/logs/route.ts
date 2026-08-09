import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { getServerSession } from "next-auth/next";
import { authOptions, isAdmin } from "@/lib/auth";

export async function GET() {
  try {
    // Lấy tối đa 500 dòng log gần nhất
    const { data, error } = await supabase
      .from('system_logs')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(500);

    if (error) {
      console.error('Error fetching logs:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Đảo ngược lại mảng để render từ trên xuống dưới (từ cũ đến mới)
    const sortedData = data ? data.reverse() : [];
    
    return NextResponse.json(sortedData);
  } catch (err) {
    console.error('Unexpected error:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

export async function DELETE() {
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
    // Xoá tất cả log
    const { error } = await supabase
      .from('system_logs')
      .delete()
      .neq('id', '00000000-0000-0000-0000-000000000000'); // Xóa tất cả với mẹo query

    if (error) {
      console.error('Error clearing logs:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error('Unexpected error:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

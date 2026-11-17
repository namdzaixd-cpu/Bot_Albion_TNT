import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";

export async function GET() {
  try {
    // Lấy metadata
    const { data: metaData } = await supabase
      .from("sp_metadata")
      .select("last_update")
      .eq("id", 1)
      .single();

    // Lấy danh sách đóng góp Siphoned
    const { data: economyData, error } = await supabase
      .from("user_economy")
      .select("user_id, silver_pieces")
      .order("silver_pieces", { ascending: false });

    if (error) {
      console.error("Lỗi lấy dữ liệu Siphoned:", error.message);
      return NextResponse.json({ error: "Không thể tải dữ liệu Siphoned." }, { status: 500 });
    }

    return NextResponse.json({
      last_update: metaData?.last_update || "Chưa có dữ liệu",
      leaderboard: economyData || []
    });
  } catch (err: any) {
    console.error("Lỗi lấy dữ liệu Siphoned:", err);
    return NextResponse.json({ error: "Không thể tải dữ liệu Siphoned." }, { status: 500 });
  }
}

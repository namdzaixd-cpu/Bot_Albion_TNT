import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabaseServer";
import { fetchAllRows } from "@/lib/fetchAllRows";

export async function GET() {
  try {
    const { data: metaData, error: metaError } = await supabase
      .from("sp_metadata")
      .select("last_update")
      .eq("id", 1)
      .maybeSingle();
    if (metaError) {
      console.error("Lỗi lấy metadata Siphoned:", metaError.message);
      return NextResponse.json({ error: "Không thể tải dữ liệu Siphoned." }, { status: 500 });
    }

    // Phân trang theo khóa bất biến user_id (silver_pieces đổi khi import làm dòng nhảy trang); sắp xếp sau khi đủ dòng.
    const economyData = await fetchAllRows<{ user_id: string; silver_pieces: number }>((from, to) =>
      supabase
        .from("user_economy")
        .select("user_id, silver_pieces", { count: "exact" })
        .order("user_id", { ascending: true })
        .range(from, to)
    );
    economyData.sort((a, b) => b.silver_pieces - a.silver_pieces || (a.user_id < b.user_id ? -1 : 1));

    return NextResponse.json({
      last_update: metaData?.last_update || "Chưa có dữ liệu",
      leaderboard: economyData
    });
  } catch (err: any) {
    console.error("Lỗi lấy dữ liệu Siphoned:", err);
    return NextResponse.json({ error: "Không thể tải dữ liệu Siphoned." }, { status: 500 });
  }
}

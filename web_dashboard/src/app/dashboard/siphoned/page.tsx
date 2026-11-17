"use client";

import { useState, useEffect, useMemo } from "react";
import { Gem, Calendar, Search, ArrowDownToLine, ArrowUpToLine, History } from "lucide-react";

export default function SiphonedDashboard() {
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [lastUpdate, setLastUpdate] = useState("Chưa có dữ liệu");
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

  useEffect(() => {
    fetch('/api/siphoned')
      .then(res => res.json())
      .then(data => {
        if (data.leaderboard) {
          setLeaderboard(data.leaderboard);
        }
        if (data.last_update) {
          setLastUpdate(data.last_update);
        }
      })
      .catch(err => console.error("Lỗi lấy dữ liệu Siphoned:", err));
  }, []);

  const filteredAndSorted = useMemo(() => {
    let result = leaderboard.filter(entry => 
      (entry.user_id ?? "").toLowerCase().includes(searchTerm.toLowerCase())
    );

    result.sort((a, b) => {
      if (sortOrder === "desc") {
        return b.silver_pieces - a.silver_pieces;
      } else {
        return a.silver_pieces - b.silver_pieces;
      }
    });

    return result;
  }, [leaderboard, searchTerm, sortOrder]);

  const totalSiphoned = leaderboard.reduce((acc, curr) => acc + curr.silver_pieces, 0);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center border border-blue-500/30">
          <Gem className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Siphoned Energy</h1>
          <p className="text-text-muted text-sm mt-1">Bảng thống kê điểm đóng góp Siphoned Energy của thành viên.</p>
        </div>
      </div>

      {/* Tổng Quan */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-sm text-text-muted font-medium mb-1">Tổng Số Người Đóng Góp</p>
            <p className="text-2xl font-bold text-white">{leaderboard.length.toLocaleString()}</p>
          </div>
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <History className="w-6 h-6 text-primary" />
          </div>
        </div>
        
        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-sm text-text-muted font-medium mb-1">Tổng Điểm Đã Thu</p>
            <p className="text-2xl font-bold text-blue-400">{totalSiphoned.toLocaleString()} SP</p>
          </div>
          <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center">
            <Gem className="w-6 h-6 text-blue-400" />
          </div>
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden flex flex-col">
        {/* Header & Controls */}
        <div className="p-4 border-b border-border bg-surface-hover/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Calendar className="w-4 h-4 text-primary" />
            <span>Mốc Log: <strong className="text-white">{lastUpdate}</strong></span>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                placeholder="Tìm tên nhân vật..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="bg-background border border-border rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary w-full sm:w-64"
              />
            </div>
            
            <button
              onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
              className="flex items-center gap-2 bg-background border border-border rounded-lg px-3 py-1.5 text-sm text-white hover:bg-surface-hover transition-colors whitespace-nowrap"
            >
              {sortOrder === "desc" ? <ArrowDownToLine className="w-4 h-4" /> : <ArrowUpToLine className="w-4 h-4" />}
              {sortOrder === "desc" ? "Cao nhất" : "Thấp nhất"}
            </button>
          </div>
        </div>

        {/* Bảng Xếp Hạng */}
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left border-collapse min-w-[500px]">
            <thead>
              <tr className="bg-background/50 border-b border-border text-xs uppercase text-text-muted tracking-wider">
                <th className="p-4 font-semibold w-20 text-center">Hạng</th>
                <th className="p-4 font-semibold">Nhân Vật (Ingame)</th>
                <th className="p-4 font-semibold text-right">Điểm Siphoned (SP)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredAndSorted.length > 0 ? (
                filteredAndSorted.map((entry, index) => {
                  // Xác định hạng thực tế (nếu đang search thì STT chỉ là tương đối của mảng search)
                  const actualRank = sortOrder === "desc" 
                    ? leaderboard.findIndex(e => e.user_id === entry.user_id) + 1
                    : leaderboard.length - leaderboard.findIndex(e => e.user_id === entry.user_id);

                  let rankStyle = "text-text-muted";
                  let rankBg = "bg-transparent";
                  if (actualRank === 1) { rankStyle = "text-yellow-900 font-bold"; rankBg = "bg-yellow-400"; }
                  else if (actualRank === 2) { rankStyle = "text-gray-900 font-bold"; rankBg = "bg-gray-300"; }
                  else if (actualRank === 3) { rankStyle = "text-orange-950 font-bold"; rankBg = "bg-orange-400"; }

                  return (
                    <tr key={entry.user_id} className="hover:bg-surface-hover/50 transition-colors">
                      <td className="p-4 text-center">
                        <span className={`inline-block w-6 h-6 rounded-full text-center leading-6 text-xs ${rankBg} ${rankStyle}`}>
                          #{actualRank}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className="font-medium text-white">{entry.user_id}</span>
                      </td>
                      <td className="p-4 text-right">
                        <span className="font-bold text-blue-400">{entry.silver_pieces.toLocaleString()}</span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={3} className="p-10 text-center text-text-muted">
                    Không tìm thấy dữ liệu đóng góp nào.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

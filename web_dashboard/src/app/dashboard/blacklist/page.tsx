"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, Trash2, Plus, UserX, Search } from "lucide-react";
import { toast } from "react-hot-toast";
import { useSession } from "next-auth/react";

export default function BlacklistDashboard() {
  const { data: session } = useSession();
  const [entries, setEntries] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  
  const [newEntry, setNewEntry] = useState({
    discord_id: "",
    ingame_name: "",
    reason: ""
  });

  const fetchBlacklist = async () => {
    try {
      const res = await fetch('/api/blacklist');
      const data = await res.json();
      if (Array.isArray(data)) setEntries(data);
    } catch (err) {
      console.error("Lỗi lấy danh sách blacklist:", err);
    }
  };

  useEffect(() => {
    fetchBlacklist();
  }, []);

  const handleAdd = async () => {
    if (!newEntry.discord_id || !newEntry.ingame_name || !newEntry.reason) {
      toast.error("Vui lòng nhập đủ thông tin!");
      return;
    }

    // Tạm thời bỏ qua việc check ID Albion qua API trên web, lưu trực tiếp
    const entryData = {
      discord_id: newEntry.discord_id,
      ingame_name: newEntry.ingame_name,
      reason: newEntry.reason
    };

    try {
      const res = await fetch('/api/blacklist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entryData)
      });
      if (res.ok) {
        toast.success("Đã thêm vào danh sách đen!");
        setNewEntry({ discord_id: "", ingame_name: "", reason: "" });
        fetchBlacklist();
      } else {
        toast.error("Lỗi khi thêm!");
      }
    } catch (err) {
      toast.error("Lỗi mạng!");
    }
  };

  const handleRemove = async (discord_id: string) => {
    if (!confirm("Bạn có chắc muốn xóa người này khỏi Blacklist?")) return;
    
    try {
      const res = await fetch(`/api/blacklist?discord_id=${discord_id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        toast.success("Đã xóa khỏi danh sách đen!");
        fetchBlacklist();
      } else {
        toast.error("Lỗi khi xóa!");
      }
    } catch (err) {
      toast.error("Lỗi mạng!");
    }
  };

  const filteredEntries = entries.filter(e => 
    e.ingame_name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
    e.discord_id?.includes(searchTerm)
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center border border-red-500/30">
          <AlertTriangle className="w-5 h-5 text-red-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Global Blacklist</h1>
          <p className="text-text-muted text-sm mt-1">Danh sách người chơi bị cấm trong toàn Liên Minh.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        
        {/* Cột Trái: Thêm Mới */}
        <div className="md:col-span-1 space-y-6">
          <div className="bg-surface border border-border rounded-xl p-5 shadow-sm space-y-4 sticky top-6">
            <h2 className="font-medium text-white flex items-center gap-2 border-b border-border pb-3">
              <UserX className="w-4 h-4 text-red-400" /> Thêm Vào Blacklist
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Tên Ingame (Albion)</label>
                <input
                  type="text"
                  value={newEntry.ingame_name}
                  onChange={e => setNewEntry({ ...newEntry, ingame_name: e.target.value })}
                  placeholder="VD: PlayerName123"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Discord ID</label>
                <input
                  type="text"
                  value={newEntry.discord_id}
                  onChange={e => setNewEntry({ ...newEntry, discord_id: e.target.value })}
                  placeholder="VD: 123456789012345678"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Lý Do Cấm</label>
                <textarea
                  value={newEntry.reason}
                  onChange={e => setNewEntry({ ...newEntry, reason: e.target.value })}
                  placeholder="VD: Scam tiền guild..."
                  rows={3}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-400 resize-none"
                />
              </div>

              <button
                onClick={handleAdd}
                className="w-full bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg py-2 text-sm font-medium transition-colors flex items-center justify-center gap-2 mt-2"
              >
                <Plus className="w-4 h-4" /> Bấm Để Cấm
              </button>
            </div>
          </div>
        </div>

        {/* Cột Phải: Danh Sách */}
        <div className="md:col-span-2 space-y-4">
          
          {/* Thanh Tìm Kiếm */}
          <div className="bg-surface border border-border rounded-xl p-3 shadow-sm flex items-center gap-3">
            <Search className="w-4 h-4 text-text-muted" />
            <input
              type="text"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              placeholder="Tìm kiếm theo Tên Ingame hoặc Discord ID..."
              className="flex-1 bg-transparent border-none text-sm text-white focus:outline-none"
            />
          </div>

          {/* Danh Sách Blacklist */}
          <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden flex flex-col min-h-[400px]">
            {filteredEntries.length > 0 ? (
              <div className="overflow-y-auto max-h-[600px] custom-scrollbar p-2 space-y-2">
                {filteredEntries.map((entry, idx) => (
                  <div key={idx} className="flex gap-4 p-4 rounded-lg bg-background border border-border hover:border-red-500/50 transition-colors">
                    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center shrink-0 border border-red-500/20">
                      <UserX className="w-5 h-5 text-red-400" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="font-bold text-white text-lg truncate">{entry.ingame_name}</h3>
                          <p className="text-sm text-text-muted font-mono mt-1">
                            Discord ID: <span className="text-white">{entry.discord_id}</span>
                          </p>
                        </div>
                        <button
                          onClick={() => handleRemove(entry.discord_id)}
                          className="text-text-muted hover:text-red-400 p-2 hover:bg-red-400/10 rounded-lg transition-colors shrink-0"
                          title="Gỡ Blacklist"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      
                      <div className="mt-3 p-3 rounded bg-red-500/5 border border-red-500/10">
                        <p className="text-sm text-gray-300">
                          <span className="font-semibold text-red-400">Lý do:</span> {entry.reason}
                        </p>
                      </div>
                      
                      <div className="mt-3 flex items-center gap-4 text-xs text-text-muted">
                        <span>⏳ {new Date(entry.timestamp).toLocaleString("vi-VN")}</span>
                        <span>👤 Cấm bởi: {entry.added_by_discord_id}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-10 opacity-50">
                <AlertTriangle className="w-16 h-16 text-text-muted mb-4" />
                <h3 className="text-lg font-bold text-white">Không Tìm Thấy Kết Quả</h3>
                <p className="text-sm text-text-muted max-w-sm mt-2">
                  Chưa có ai trong danh sách đen hoặc không khớp với từ khóa tìm kiếm.
                </p>
              </div>
            )}
          </div>
          
        </div>
      </div>
    </div>
  );
}

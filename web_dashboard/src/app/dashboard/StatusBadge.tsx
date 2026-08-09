"use client";

import { useState, useEffect } from "react";

/**
 * Chấm trạng thái bot, đồng bộ với heartbeat thực tế từ Render (bảng json_storage).
 * Lớn, dễ nhìn, tự cập nhật mỗi 15s.
 */
export default function StatusBadge() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [lastSeen, setLastSeen] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const res = await fetch("/api/bot-status");
        if (!res.ok) return;
        const d = await res.json();
        if (!mounted) return;
        setOnline(d.online);
        setLastSeen(d.last_seen);
      } catch { }
    };
    check();
    const iv = setInterval(check, 15_000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  const isLoading = online === null;
  const color = isLoading ? "#8b8499" : online ? "#4ade80" : "#fb7185";
  const label = isLoading ? "Đang kiểm tra..." : online ? "HỆ THỐNG ONLINE" : "BOT OFFLINE";
  const dot = isLoading
    ? "w-3 h-3 rounded-full bg-[#8b8499] animate-pulse"
    : `w-3 h-3 rounded-full ${online ? "bg-green-400 animate-pulse" : "bg-rose-500"}`;

  return (
    <div className="flex items-center gap-3">
      <span className={dot} style={online ? { boxShadow: "0 0 12px rgba(74,222,128,.8)" } : {}} />
      <div className="leading-tight">
        <div className="text-lg font-black tracking-wide" style={{ color }}>
          {label}
        </div>
        <div className="text-[11px]" style={{ color: "#8b8499" }}>
          {lastSeen && online
            ? `Cập nhật ${new Date(lastSeen).toLocaleTimeString("vi-VN")}`
            : online ? "" : "Bot không đập tim > 90s"}
        </div>
      </div>
    </div>
  );
}

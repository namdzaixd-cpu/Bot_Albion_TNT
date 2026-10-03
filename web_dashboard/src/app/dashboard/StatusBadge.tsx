"use client";

import { useState, useEffect } from "react";


export default function StatusBadge() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [lastSeen, setLastSeen] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const response = await fetch("/api/bot-status", { cache: "no-store" });
        if (!mounted) return;
        if (!response.ok) {
          setOnline(null);
          setLastSeen(null);
          setUnavailable(true);
          return;
        }
        const payload: unknown = await response.json();
        if (!payload || typeof payload !== "object" || !("main_bot" in payload)) {
          setOnline(null);
          setLastSeen(null);
          setUnavailable(true);
          return;
        }
        const mainBot = payload.main_bot;
        if (!mainBot || typeof mainBot !== "object" || !("online" in mainBot) ||
            typeof mainBot.online !== "boolean") {
          setOnline(null);
          setLastSeen(null);
          setUnavailable(true);
          return;
        }
        const lastSeen = "last_seen" in mainBot && typeof mainBot.last_seen === "string"
          ? mainBot.last_seen
          : null;
        setOnline(mainBot.online);
        setLastSeen(lastSeen);
        setUnavailable(false);
      } catch {
        if (mounted) {
          setOnline(null);
          setLastSeen(null);
          setUnavailable(true);
        }
      }
    };
    check();
    const interval = setInterval(check, 15_000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const isLoading = online === null && !unavailable;
  const isUnknown = unavailable && online === null;
  const color = isLoading || isUnknown ? "#8b8499" : online ? "#4ade80" : "#fb7185";
  const label = isLoading
    ? "Đang kiểm tra..."
    : isUnknown
      ? "Không lấy được trạng thái"
      : online
        ? "HỆ THỐNG ONLINE"
        : "BOT OFFLINE";
  const dot = isLoading
    ? "w-3 h-3 rounded-full bg-[#8b8499] animate-pulse"
    : `w-3 h-3 rounded-full ${isUnknown ? "bg-[#8b8499]" : online ? "bg-green-400 animate-pulse" : "bg-rose-500"}`;

  return (
    <div className="flex items-center gap-3" aria-live="polite">
      <span className={dot} style={online ? { boxShadow: "0 0 12px rgba(74,222,128,.8)" } : {}} />
      <div className="leading-tight">
        <div className="text-lg font-black tracking-wide" style={{ color }}>
          {label}
        </div>
        <div className="text-[11px]" style={{ color: "#8b8499" }}>
          {lastSeen && online
            ? `Cập nhật ${new Date(lastSeen).toLocaleTimeString("vi-VN")}`
            : isUnknown ? "API chưa xác nhận trạng thái bot" : online ? "" : "Bot không đập tim > 90s"}
        </div>
      </div>
    </div>
  );
}

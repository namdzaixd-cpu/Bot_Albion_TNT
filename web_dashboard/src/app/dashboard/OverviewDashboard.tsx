"use client";

import { useState, useEffect, useRef } from "react";
import { Users, Activity, ToggleLeft } from "lucide-react";
import StatusBadge from "./StatusBadge";

type Activity = { time: string; event: string; module: string; status: string };
type ModuleState = { key: string; id: string; enabled: boolean };

/** Tên tiếng Việt cho từng module; chưa có thì tự chuyển từ id. */
const MODULE_LABELS: Record<string, string> = {
  onboard: "Recruiter (Onboarding)",
  onboarding: "Recruiter (Onboarding)",
  guildcheck: "GuildCheck System",
  massing: "Massing / CTA",
  siphoned: "Siphoned Energy",
  blacklist: "Blacklist",
  corebank: "Quản lý Core-Bank",
  ai: "AI Assistant & TTS",
  vision: "AI Vision",
  tts: "Text-to-Speech",
  logs: "System Logs",
};

const labelOf = (id: string) =>
  MODULE_LABELS[id] ??
  id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const fmtNum = (n: number) =>
  n >= 1_000_000 ? (n / 1_000_000).toFixed(1) + "M"
  : n >= 1_000 ? (n / 1_000).toFixed(1) + "k"
  : n.toString();

const fmtTime = (iso: string) => {
  try { return new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
};

// Count-up hook
function useCountUp(target: number, dur = 900) {
  const [val, setVal] = useState(0);
  const raf = useRef<number | undefined>(undefined);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(Math.round(target * eased));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target, dur]);
  return val;
}

function StatCard({ label, value, sub, icon: Icon, color, raw }: {
  label: string; value: number; sub: string;
  icon: React.ElementType; color: string; raw?: string | null;
}) {
  const v = useCountUp(value);
  return (
    <div className="glass relative overflow-hidden rounded-2xl p-5 group hover:-translate-y-1 transition-all duration-300"
      style={{ boxShadow: `0 0 0 1px rgba(168,85,247,.12), 0 10px 40px rgba(0,0,0,.4)` }}>
      <div className="relative flex items-start justify-between">
        <div>
          <span className="text-sm" style={{ color: "#8b8499" }}>{label}</span>
          <div className="count-pop mt-3 text-4xl font-black tabular-nums" style={{ color }}>
            {raw ?? fmtNum(v)}
          </div>
          <div className="mt-1 text-xs" style={{ color: "#8b8499" }}>{sub}</div>
        </div>
        <div className="w-11 h-11 rounded-xl grid place-items-center shrink-0"
          style={{ background: `${color}1f`, boxShadow: `0 0 16px ${color}55`, color }}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}

export default function OverviewDashboard() {
  const [stats, setStats] = useState<{
    members: number | null; members_live: boolean;
    corebank_total: number; blacklist_count: number; ai_today: number;
  }>({ members: null, members_live: false, corebank_total: 0, blacklist_count: 0, ai_today: 0 });
  const [modules, setModules] = useState<ModuleState[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await fetch("/api/overview");
      if (res.ok) {
        const d = await res.json();
        setStats(d.stats);
        setModules(d.modules ?? []);
        setActivity(d.activity);
      }
    } catch { }
  };

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      await load();
      if (mounted) setLoading(false);
    };
    run();
    const iv = setInterval(() => { if (mounted) load(); }, 15000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  const onCount = modules.filter((m) => m.enabled).length;

  return (
    <div className="space-y-8 animate-fade-in relative z-10">
      {/* Hero */}
      <div className="glass rounded-3xl p-8 flex items-center gap-6 relative overflow-hidden">
        {/* compact spinning core as accent, not blocking text */}
        <div className="relative w-20 h-20 shrink-0 hidden sm:block">
          <div className="core-spin absolute inset-0 rounded-full border border-dashed border-[rgba(168,85,247,.4)]" />
          <div className="core-rev absolute inset-2 rounded-full border border-dashed border-[rgba(34,211,238,.35)]" />
          <div className="pulse-core absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-gradient-to-br from-[#a855f7] to-[#22d3ee] grid place-items-center text-xl">⚔️</div>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-4xl font-black tracking-tight neon-purple">BOT TNC</h2>
            <span className="text-xs px-2 py-1 rounded-full border border-[rgba(34,211,238,.4)] text-[#22d3ee]" style={{ boxShadow: "0 0 12px rgba(34,211,238,.25)" }}>v2.1</span>
          </div>
          <p className="mt-2 text-sm max-w-xl" style={{ color: "#8b8499" }}>
            Guild Assistant đang bảo vệ{" "}
            <span className="neon-cyan font-bold">
              {stats.members !== null ? stats.members.toLocaleString("vi-VN") : "—"}
            </span>{" "}
            chiến binh Albion. Mọi module vận hành{" "}
            <span className="neon-rose font-bold">real-time</span>.
          </p>
          <div className="mt-3 flex items-center gap-2 text-xs" style={{ color: "#8b8499" }}>
            <StatusBadge />
          </div>
        </div>
      </div>

      {/* Thành viên + Module */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <StatCard
          label="Thành viên"
          value={stats.members ?? 0}
          raw={stats.members === null ? "—" : undefined}
          sub={stats.members_live ? "Số liệu trực tiếp từ Discord" : "Chưa lấy được số liệu"}
          icon={Users}
          color="#8b9cff"
        />

        {/* Ô tổng: danh sách module đang có */}
        <div className="glass rounded-2xl p-5 lg:col-span-2"
          style={{ boxShadow: "0 0 0 1px rgba(168,85,247,.12), 0 10px 40px rgba(0,0,0,.4)" }}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm flex items-center gap-2" style={{ color: "#8b8499" }}>
              <ToggleLeft className="w-4 h-4" style={{ color: "#a855f7" }} />
              Module hệ thống
            </span>
            <span className="text-xs font-semibold tabular-nums" style={{ color: "#8b8499" }}>
              <span style={{ color: onCount > 0 ? "#4ade80" : "#8b8499" }}>{onCount}</span>
              {" / "}{modules.length} đang bật
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="h-10 rounded-xl bg-[rgba(139,156,255,.08)] animate-pulse" />
              ))}
            </div>
          ) : modules.length === 0 ? (
            <div className="text-center py-6 text-sm" style={{ color: "#8b8499" }}>
              Chưa có module nào trong cấu hình.
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {modules.map((m) => (
                <div
                  key={m.key}
                  className="flex items-center gap-2.5 rounded-xl border px-3 py-2.5 transition-colors"
                  style={{
                    borderColor: m.enabled ? "rgba(74,222,128,.28)" : "rgba(168,85,247,.12)",
                    background: m.enabled ? "rgba(74,222,128,.07)" : "rgba(7,6,15,.4)",
                  }}
                  title={m.enabled ? "Đang bật" : "Đã tắt"}
                >
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${m.enabled ? "animate-pulse" : ""}`}
                    style={{
                      background: m.enabled ? "#4ade80" : "#4b4458",
                      boxShadow: m.enabled ? "0 0 8px rgba(74,222,128,.7)" : "none",
                    }}
                  />
                  <span
                    className="text-xs truncate"
                    style={{ color: m.enabled ? "#dbeafe" : "#8b8499" }}
                  >
                    {labelOf(m.id)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Activity */}
      <div className="glass rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: "#b9c2ff" }}>
            <Activity className="w-5 h-5" style={{ color: "#8b9cff" }} /> Hoạt động gần đây
          </h2>
          <span className="text-xs flex items-center gap-1.5" style={{ color: "#8b8499" }}>
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" /> Real-time
          </span>
        </div>
        {loading ? (
          <div className="space-y-3">{[1, 2, 3].map((i) => <div key={i} className="h-12 rounded-xl bg-[rgba(139,156,255,.08)] animate-pulse" />)}</div>
        ) : activity.length === 0 ? (
          <div className="text-center py-12" style={{ color: "#8b8499" }}>
            <div className="text-4xl mb-3 opacity-50">📡</div>
            Chưa có tín hiệu hoạt động. Hãy chờ guild thức giấc...
          </div>
        ) : (
          <div className="space-y-2">
            {activity.map((a, i) => (
              <div key={i} className="flex items-center gap-4 rounded-xl border border-[rgba(168,85,247,.12)] bg-[rgba(7,6,15,.4)] px-4 py-3 hover:bg-[rgba(168,85,247,.08)] transition-colors">
                <span className="text-xs font-mono w-12" style={{ color: "#8b8499" }}>{fmtTime(a.time)}</span>
                <span className="flex-1 text-sm text-white/90 truncate">{a.event}</span>
                <span className="text-xs px-2.5 py-1 rounded-md bg-[rgba(168,85,247,.12)]" style={{ color: "#d8b4fe" }}>{a.module}</span>
                <span className={`text-xs px-2.5 py-1 rounded-md ${a.status === "ok" || a.status === "OK" ? "bg-green-500/15 text-green-400" : "bg-rose-500/15 text-rose-400"}`}>{a.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

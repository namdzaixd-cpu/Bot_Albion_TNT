"use client";

import { useState, useEffect } from "react";
import { Shield, Users, Swords, Crown, Skull, Trophy } from "lucide-react";

type Guild = {
  name: string; founder: string; founded: string; alliance: string | null;
  killFame: number; deathFame: number; attacksWon: number; defensesWon: number;
  memberCount: number;
  stats: { kills?: number; deaths?: number; fame?: number; ratio?: string | number };
  topPlayers: { name: string; killFame: number; deathFame: number }[];
  members: { name: string; killFame: number }[];
  updated_at: string;
};

const fmt = (n: number) =>
  n >= 1_000_000 ? (n / 1_000_000).toFixed(2) + "M"
  : n >= 1_000 ? (n / 1_000).toFixed(1) + "k" : n.toString();

function Stat({ label, value, icon: Icon, color }: {
  label: string; value: string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="glass rounded-2xl p-5" style={{ boxShadow: "0 0 0 1px rgba(168,85,247,.12)" }}>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: `${color}1f`, color }}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-2xl font-black tabular-nums" style={{ color }}>{value}</div>
          <div className="text-xs" style={{ color: "#8b8499" }}>{label}</div>
        </div>
      </div>
    </div>
  );
}

export default function GuildCheckPanel() {
  const [g, setG] = useState<Guild | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await fetch("/api/guildcheck");
      if (!res.ok) throw new Error("Không lấy được dữ liệu guild");
      setG(await res.json());
    } catch (e: any) {
      setErr(e.message || "Lỗi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); const iv = setInterval(load, 120_000); return () => clearInterval(iv); }, []);

  if (loading) return <div className="glass rounded-2xl p-10 text-center" style={{ color: "#8b8499" }}>Đang tải dữ liệu guild từ Albion...</div>;
  if (err || !g) return <div className="glass rounded-2xl p-10 text-center text-rose-400">{err || "Không có dữ liệu"}</div>;

  return (
    <div className="space-y-6 animate-fade-in relative z-10">
      {/* Header guild */}
      <div className="glass rounded-3xl p-8 flex items-center gap-6 relative overflow-hidden"
        style={{ boxShadow: "0 0 0 1px rgba(168,85,247,.12)" }}>
        <div className="relative w-20 h-20 shrink-0 hidden sm:block rounded-full bg-gradient-to-br from-[#a855f7] to-[#22d3ee] grid place-items-center text-4xl">🛡️</div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-black neon-purple">{g.name}</h2>
            {g.alliance && <span className="text-xs px-2 py-1 rounded-full border border-[rgba(34,211,238,.4)] text-[#22d3ee]">[{g.alliance}]</span>}
          </div>
          <p className="mt-2 text-sm" style={{ color: "#8b8499" }}>
            👑 Founder: <span className="text-white/90">{g.founder}</span> · Thành lập: {new Date(g.founded).toLocaleDateString("vi-VN")}
          </p>
          <p className="mt-1 text-xs" style={{ color: "#8b8499" }}>
            🕒 Cập nhật: {new Date(g.updated_at).toLocaleTimeString("vi-VN")} · Nguồn: Albion Online API
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Thành viên" value={fmt(g.memberCount)} icon={Users} color="#8b9cff" />
        <Stat label="Kill Fame" value={fmt(g.killFame)} icon={Trophy} color="#fbbf77" />
        <Stat label="Death Fame" value={fmt(g.deathFame)} icon={Skull} color="#fb7185" />
        <Stat label="Tỷ lệ K/D" value={fmt(Number(g.stats?.ratio) || 0)} icon={Swords} color="#67e8f9" />
      </div>

      {/* Top players */}
      <div className="glass rounded-2xl p-6" style={{ boxShadow: "0 0 0 1px rgba(168,85,247,.12)" }}>
        <h3 className="text-lg font-semibold flex items-center gap-2 mb-4" style={{ color: "#b9c2ff" }}>
          <Crown className="w-5 h-5" style={{ color: "#fbbf77" }} /> Top chiến binh (Kill Fame)
        </h3>
        <div className="space-y-2">
          {g.topPlayers.map((p, i) => (
            <div key={p.name} className="flex items-center gap-4 rounded-xl border border-[rgba(168,85,247,.12)] bg-[rgba(7,6,15,.4)] px-4 py-3">
              <span className="w-7 text-center font-black" style={{ color: "#a855f7" }}>{i + 1}</span>
              <span className="flex-1 text-sm text-white/90">{p.name}</span>
              <span className="text-xs" style={{ color: "#fbbf77" }}>{fmt(p.killFame)} KF</span>
              <span className="text-xs" style={{ color: "#fb7185" }}>{fmt(p.deathFame)} DF</span>
            </div>
          ))}
          {g.topPlayers.length === 0 && <div className="text-center py-6 text-sm" style={{ color: "#8b8499" }}>Chưa có dữ liệu.</div>}
        </div>
      </div>
    </div>
  );
}

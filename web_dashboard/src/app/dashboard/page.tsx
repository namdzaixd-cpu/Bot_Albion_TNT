"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useSession, signIn } from "next-auth/react";
import SearchableSelect, { Option } from "@/components/SearchableSelect";
import AIDashboard from "./ai/page";
import LogsDashboard from "./logs/page";
import CoreBankDashboard from "./corebank/page";
import BlacklistDashboard from "./blacklist/page";
import SiphonedDashboard from "./siphoned/page";
import OverviewDashboard from "./OverviewDashboard";
import CommandPalette from "./CommandPalette";
import {
  LayoutDashboard, Users, Shield,
  Swords, Gem, AlertTriangle, Package, Bot, ChevronLeft, Power, CheckCircle2, XCircle, Settings2, Ban, Terminal, PanelLeftClose, PanelLeft
} from "lucide-react";

const MODULES = [
  { id: 'overview', name: 'Tổng quan', icon: LayoutDashboard },
  { id: 'onboarding', name: 'Recruiter (Onboarding)', icon: Users },
  { id: 'guildcheck', name: 'GuildCheck System', icon: Shield },
  { id: 'massing', name: 'Massing / CTA', icon: Swords },
  { id: 'siphoned', name: 'Siphoned Energy', icon: Gem },
  { id: 'blacklist', name: 'Global Blacklist', icon: Ban },
  { id: 'corebank', name: 'Quản lý Core-Bank', icon: Package },
  { id: 'ai', name: 'AI Assistant & TTS', icon: Bot },
  { id: 'logs', name: 'System Logs', icon: Terminal }
];

export default function Dashboard() {
  const { data: session, status } = useSession();
  const [activeModule, setActiveModule] = useState('overview');
  const [collapsed, setCollapsed] = useState(false);

  // API Data State
  const [isOnboardEnabled, setIsOnboardEnabled] = useState(false);
  const [config, setConfig] = useState({
    apply_channel_id: "",
    question_channel_id: "",
    rules_channel_id: "",
    chat_channel_id: "",
    officer_role_id: "",
    member_role_id: ""
  });
  const [loading, setLoading] = useState(true);

  // Discord Data
  const [discordChannels, setDiscordChannels] = useState<Option[]>([]);
  const [discordRoles, setDiscordRoles] = useState<Option[]>([]);

  // Fetch from API
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch('/api/config');
        if (res.ok) {
          const data = await res.json();
          setIsOnboardEnabled(data.is_onboard_enabled ?? false);
          setConfig({
            apply_channel_id: data.apply_channel_id || "",
            question_channel_id: data.question_channel_id || "",
            rules_channel_id: data.rules_channel_id || "",
            chat_channel_id: data.chat_channel_id || "",
            officer_role_id: data.officer_role_id || "",
            member_role_id: data.member_role_id || ""
          });
        }

        // Fetch discord data
        const discordRes = await fetch('/api/discord-data');
        if (discordRes.ok) {
          const discordData = await discordRes.json();
          // Only keep text channels for applying/questions (type 0 or 15 etc, but we'll show all for simplicity, or just map them)
          setDiscordChannels(discordData.channels || []);
          setDiscordRoles(discordData.roles || []);
        }
      } catch (err) {
        console.error("Lỗi lấy data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, []);

  const handleConfigChange = async (field: string, value: string) => {
    setConfig(prev => ({ ...prev, [field]: value }));
    try {
      await fetch('/api/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value })
      });
    } catch (err) {
      console.error("Lỗi lưu config:", err);
    }
  };

  const handleToggle = async () => {
    const newVal = !isOnboardEnabled;
    setIsOnboardEnabled(newVal);
    try {
      await fetch('/api/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_onboard_enabled: newVal })
      });
    } catch (err) {
      console.error("Lỗi toggle config:", err);
    }
  };


  // ── Chặn truy cập khi chưa đăng nhập ────────────────────────────────────
  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-text-muted">
        Đang kiểm tra đăng nhập...
      </div>
    );
  }

  if (status === "unauthenticated") {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-6 bg-background px-6 text-center">
        <Shield className="w-14 h-14 text-[#5865F2]" />
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Khu vực quản trị</h1>
          <p className="text-text-muted max-w-md">
            Bạn cần đăng nhập bằng Discord để xem và chỉnh sửa cấu hình bot.
          </p>
        </div>
        <button
          onClick={() => signIn("discord")}
          className="bg-[#5865F2] hover:bg-[#4752C4] text-white px-6 py-3 rounded-lg font-semibold transition-colors shadow-lg shadow-[#5865F2]/20"
        >
          Đăng nhập bằng Discord
        </button>
        <Link href="/" className="text-sm text-text-muted hover:text-white transition-colors">
          ← Về trang chủ
        </Link>
      </div>
    );
  }
  // ────────────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <CommandPalette onSelect={setActiveModule} />
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-20' : 'w-72'} border-r border-[rgba(168,85,247,.15)] bg-[rgba(20,18,31,.5)] backdrop-blur-xl flex flex-col transition-all duration-300 relative z-10`}>
        <div className="h-16 flex items-center px-6 border-b border-[rgba(168,85,247,.12)] justify-between">
          <Link href="/" className="flex items-center gap-3 text-[#8b8499] hover:text-white transition-colors">
            <ChevronLeft className="w-5 h-5" />
            {!collapsed && <span className="font-semibold text-sm">Về trang chủ</span>}
          </Link>
          <button onClick={() => setCollapsed((c) => !c)} className="text-[#8b8499] hover:text-[#d8b4fe] transition-colors" title="Thu gọn">
            {collapsed ? <PanelLeft className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
          </button>
        </div>

        <div className="p-6">
          <h2 className={`text-xs font-bold text-[#8b8499] uppercase tracking-wider mb-4 flex items-center gap-2 ${collapsed ? 'justify-center' : ''}`}>
            <LayoutDashboard className="w-4 h-4" style={{ color: "#a855f7" }} />
            {!collapsed && <span className="neon-purple">Guild Assistant</span>}
          </h2>
          <nav className="space-y-2">
            {MODULES.map((mod) => (
              <button
                key={mod.id}
                onClick={() => setActiveModule(mod.id)}
                title={collapsed ? mod.name : undefined}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${collapsed ? 'justify-center' : ''} ${activeModule === mod.id
                    ? 'bg-[rgba(168,85,247,.18)] text-[#d8b4fe] font-semibold shadow-[0_0_20px_rgba(168,85,247,.35)] border border-[rgba(168,85,247,.4)]'
                    : 'text-[#8b8499] hover:bg-[rgba(168,85,247,.08)] hover:text-white border border-transparent'
                  }`}
              >
                <mod.icon className={`w-5 h-5 ${activeModule === mod.id ? 'text-[#d8b4fe]' : 'text-[#8b8499]'}`} />
                {!collapsed && <span className="text-sm">{mod.name}</span>}
              </button>
            ))}
          </nav>
        </div>

        {/* User Profile */}
        <div className="mt-auto p-6 border-t border-border/50">
          <div className="flex items-center gap-3 glass-panel p-3 rounded-xl">
            <img src={session?.user?.image || 'https://cdn.discordapp.com/embed/avatars/0.png'} alt="Avatar" className="w-10 h-10 rounded-full border border-border" />
            <div className="overflow-hidden">
              <p className="text-sm font-bold text-white truncate">{session?.user?.name || 'Guest'}</p>
              <p className="text-xs text-text-muted truncate">{(session?.user as { isAdmin?: boolean })?.isAdmin ? 'Quản trị viên' : 'Chỉ xem'}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col bg-transparent relative">
        {/* floating particles (fixed seed, no random to avoid hydration mismatch) */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          {[
            { l: 12, w: 5, h: 6, d: 14, delay: 1 },
            { l: 28, w: 7, h: 5, d: 18, delay: 3 },
            { l: 45, w: 4, h: 7, d: 12, delay: 0.5 },
            { l: 63, w: 6, h: 6, d: 16, delay: 2 },
            { l: 78, w: 5, h: 5, d: 13, delay: 4 },
            { l: 88, w: 7, h: 6, d: 17, delay: 1.5 },
            { l: 5, w: 6, h: 5, d: 15, delay: 3.5 },
            { l: 35, w: 5, h: 7, d: 19, delay: 2.5 },
            { l: 55, w: 7, h: 6, d: 11, delay: 0.8 },
            { l: 72, w: 4, h: 5, d: 14, delay: 4.2 },
            { l: 18, w: 6, h: 6, d: 16, delay: 1.2 },
            { l: 92, w: 5, h: 7, d: 13, delay: 3.8 },
            { l: 50, w: 7, h: 5, d: 18, delay: 0.3 },
            { l: 68, w: 5, h: 6, d: 15, delay: 2.7 },
          ].map((p, i) => (
            <span key={i} className="particle"
              style={{ left: `${p.l}%`, width: p.w, height: p.h, animationDuration: `${p.d}s`, animationDelay: `${p.delay}s` }} />
          ))}
        </div>

        {/* Header */}
        <header className="h-20 flex items-center justify-between px-10 border-b border-[rgba(168,85,247,.12)] z-10 relative">
          <div>
            <h1 className="text-2xl font-bold neon-purple">{activeModule === 'overview' ? 'Tổng Quan' : 'Cấu Hình Module'}</h1>
            <p className="text-sm mt-1" style={{ color: "#8b8499" }}>Điều khiển guild từ một bảng điều khiển.</p>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold text-text-muted">Trạng thái Module:</span>
            <button
              onClick={handleToggle}
              className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors duration-300 focus:outline-none ${isOnboardEnabled ? 'bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.4)]' : 'bg-surface'
                }`}
            >
              <span
                className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform duration-300 ${isOnboardEnabled ? 'translate-x-9' : 'translate-x-1'
                  }`}
              />
            </button>
            <span className={`text-sm font-bold ${isOnboardEnabled ? 'text-green-400' : 'text-text-muted'}`}>
              {isOnboardEnabled ? 'Đang Bật' : 'Đã Tắt'}
            </span>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 p-10 overflow-y-auto custom-scrollbar z-10 relative">
          {activeModule === 'overview' ? (
            <div className="max-w-6xl mx-auto">
              <div className="mb-6">
                <h1 className="text-2xl font-bold text-white">Tổng quan</h1>
                <p className="text-sm text-text-muted mt-1">Hoạt động bot theo thời gian thực</p>
              </div>
              <OverviewDashboard />
            </div>
          ) : activeModule === 'onboarding' ? (
            <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">

              <div className="glass-panel p-8 rounded-2xl border-primary/20">
                <div className="flex items-start gap-6">
                  <div className="w-16 h-16 rounded-2xl bg-primary/20 border border-primary/30 flex items-center justify-center text-3xl">
                    👋
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold text-white">Recruiter (Onboarding)</h2>
                    <p className="text-text-muted mt-2 leading-relaxed">
                      Tính năng duyệt đơn tự động. Cho phép cấu hình kênh tiếp đón, kênh phỏng vấn và cài đặt vai trò tự động.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                {/* Lệnh / Cấu hình */}
                <div className="space-y-6">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Settings2 className="w-5 h-5 text-primary" />
                    Các Cấu Hình (Lệnh)
                  </h3>

                  {/* Item 1 */}
                  <div className="glass-panel p-5 rounded-xl space-y-4 hover:border-primary/50 transition-colors">
                    <div>
                      <code className="text-primary font-mono text-xs bg-primary/10 px-2 py-1 rounded">/recuibot set_apply_channel</code>
                      <p className="text-sm font-medium mt-2">Kênh nộp đơn (Channel muốn bot hoạt động)</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <SearchableSelect
                        options={discordChannels}
                        value={config.apply_channel_id}
                        onChange={(val) => handleConfigChange('apply_channel_id', val)}
                        placeholder="-- Chọn Kênh Nộp Đơn --"
                      />
                    </div>
                  </div>

                  {/* Item 2 */}
                  <div className="glass-panel p-5 rounded-xl space-y-4 hover:border-primary/50 transition-colors">
                    <div>
                      <code className="text-primary font-mono text-xs bg-primary/10 px-2 py-1 rounded">/recuibot setup_channels</code>
                      <p className="text-sm font-medium mt-2">Cấu hình bộ 3 kênh tiếp đón</p>
                    </div>
                    <div className="space-y-3">
                      <SearchableSelect
                        options={discordChannels}
                        value={config.rules_channel_id}
                        onChange={(val) => handleConfigChange('rules_channel_id', val)}
                        placeholder="-- Chọn Kênh Luật Lệ (Rules) --"
                      />
                      <SearchableSelect
                        options={discordChannels}
                        value={config.chat_channel_id}
                        onChange={(val) => handleConfigChange('chat_channel_id', val)}
                        placeholder="-- Chọn Kênh Trò Chuyện (Guild Chat) --"
                      />
                      <SearchableSelect
                        options={discordChannels}
                        value={config.question_channel_id}
                        onChange={(val) => handleConfigChange('question_channel_id', val)}
                        placeholder="-- Chọn Kênh Phỏng Vấn (Hỏi Đáp) --"
                      />
                    </div>
                  </div>

                  {/* Item 3 */}
                  <div className="glass-panel p-5 rounded-xl space-y-4 hover:border-primary/50 transition-colors">
                    <div>
                      <code className="text-primary font-mono text-xs bg-primary/10 px-2 py-1 rounded">/recuibot setup_roles</code>
                      <p className="text-sm font-medium mt-2">Cấu hình Roles nhận được</p>
                    </div>
                    <div className="space-y-3">
                      <SearchableSelect
                        options={discordRoles}
                        value={config.officer_role_id}
                        onChange={(val) => handleConfigChange('officer_role_id', val)}
                        placeholder="-- Chọn Officer Role --"
                        isRole={true}
                      />
                      <SearchableSelect
                        options={discordRoles}
                        value={config.member_role_id}
                        onChange={(val) => handleConfigChange('member_role_id', val)}
                        placeholder="-- Chọn Member Role --"
                        isRole={true}
                      />
                    </div>
                  </div>

                </div>

                {/* Trạng thái hiện tại */}
                <div className="space-y-6">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Power className="w-5 h-5 text-primary" />
                    Trạng Thái Cấu Hình
                  </h3>

                  <div className="space-y-3 relative">

                    {/* Status 1 */}
                    <div className={`p-4 rounded-xl border ${config.apply_channel_id ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'} flex items-center gap-4 transition-colors`}>
                      {config.apply_channel_id ? <CheckCircle2 className="text-green-400 w-6 h-6" /> : <XCircle className="text-red-400 w-6 h-6" />}
                      <div>
                        <p className={`font-semibold ${config.apply_channel_id ? 'text-green-400' : 'text-red-400'}`}>
                          {config.apply_channel_id ? 'Đang hoạt động' : 'Thiếu thông tin'}
                        </p>
                        <p className="text-xs text-text-muted mt-1">Kênh nộp đơn: {config.apply_channel_id || 'Chưa thiết lập'}</p>
                      </div>
                    </div>

                    {/* Status 2 */}
                    <div className={`p-4 rounded-xl border ${config.question_channel_id ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'} flex items-center gap-4 transition-colors`}>
                      {config.question_channel_id ? <CheckCircle2 className="text-green-400 w-6 h-6" /> : <XCircle className="text-red-400 w-6 h-6" />}
                      <div>
                        <p className={`font-semibold ${config.question_channel_id ? 'text-green-400' : 'text-red-400'}`}>
                          {config.question_channel_id ? 'Đang hoạt động' : 'Thiếu thông tin'}
                        </p>
                        <p className="text-xs text-text-muted mt-1">Kênh phỏng vấn: {config.question_channel_id || 'Chưa thiết lập'}</p>
                      </div>
                    </div>

                    {/* Status 3 */}
                    <div className={`p-4 rounded-xl border ${config.officer_role_id && config.member_role_id ? 'bg-green-500/10 border-green-500/30' : 'bg-yellow-500/10 border-yellow-500/30'} flex items-center gap-4 transition-colors`}>
                      {config.officer_role_id && config.member_role_id ? <CheckCircle2 className="text-green-400 w-6 h-6" /> : <AlertTriangle className="text-yellow-400 w-6 h-6" />}
                      <div>
                        <p className={`font-semibold ${config.officer_role_id && config.member_role_id ? 'text-green-400' : 'text-yellow-400'}`}>
                          {config.officer_role_id && config.member_role_id ? 'Đang hoạt động' : 'Thiếu thông tin (Roles)'}
                        </p>
                        <p className="text-xs text-text-muted mt-1">
                          Officer: {config.officer_role_id ? '✅' : '❌'} | Member: {config.member_role_id ? '✅' : '❌'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          ) : activeModule === 'ai' ? (
            <div className="animate-fade-in">
              <AIDashboard />
            </div>
          ) : activeModule === 'corebank' ? (
            <div className="animate-fade-in">
              <CoreBankDashboard />
            </div>
          ) : activeModule === 'blacklist' ? (
            <div className="animate-fade-in">
              <BlacklistDashboard />
            </div>
          ) : activeModule === 'siphoned' ? (
            <div className="animate-fade-in">
              <SiphonedDashboard />
            </div>
          ) : activeModule === 'logs' ? (
            <div className="animate-fade-in h-full">
              <LogsDashboard />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in opacity-50">
              <Package className="w-24 h-24 text-text-muted mb-6" />
              <h2 className="text-2xl font-bold text-white mb-2">Tính Năng Đang Phát Triển</h2>
              <p className="text-text-muted max-w-md">
                Giao diện quản lý cấu hình cho {MODULES.find(m => m.id === activeModule)?.name} hiện đang được xây dựng. Vui lòng quay lại sau!
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

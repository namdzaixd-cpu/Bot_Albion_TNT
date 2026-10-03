"use client";

import { useEffect, useState } from "react";
import { signIn, signOut, useSession } from "next-auth/react";
import Link from "next/link";

interface BlacklistEntry {
  discord_id: string;
  ingame_name: string;
  ingame_id: string;
  reason: string;
  added_by_discord_id: string;
  timestamp: string;
  source_guild_id: string;
}

const FEATURES = [
  { 
    title: "👋 Onboarding (Recuibot)", 
    desc: "Tự động tính Fame qua API, duyệt đơn thành viên mới.", 
    icon: "👋",
    details: "Cơ chế hoạt động chi tiết: Hệ thống cung cấp luồng phỏng vấn tự động.\n1. Thành viên mới nộp ảnh chỉ số Ingame. Bot lập tức gọi API Albion tính tổng Fame (PvE, PvP, Crafting) và quét Blacklist.\n2. Bot gửi mẫu hướng dẫn tự động yêu cầu người chơi đọc nội quy, và đổi tên Discord theo đúng chuẩn Form: '[TNC] Tên_Ingame Năm_Sinh'.\n3. Yêu cầu ứng viên nộp đơn (Apply) trực tiếp vào guild 'The Northern Constellations' trong game.\n4. Sau khi Officer xác nhận duyệt đơn ingame, thành viên ping Officer để được cấp Role chính thức trên Discord. Quy trình khép kín, an toàn tuyệt đối!",
    commands: [
      { cmd: "/recuibot setup_channels", desc: "Cấu hình ID kênh nội quy, guild-chat và hỏi đáp." },
      { cmd: "/recuibot set_apply_channel", desc: "Định cấu hình kênh nộp đơn." },
      { cmd: "/recuibot setup_roles", desc: "Cài đặt role sẽ nhận được khi được duyệt." },
      { cmd: "/recuibot toggle", desc: "Bật/tắt tính năng nhận đơn ứng tuyển." },
      { cmd: "/recuibot list", desc: "Xem cấu hình và đơn đang chờ duyệt." }
    ]
  },
  { 
    title: "🛡️ GuildCheck System", 
    desc: "Rà soát thành viên out guild và đối chiếu dữ liệu ingame.", 
    icon: "🛡️",
    details: "Cơ chế hoạt động: Tính năng GuildCheck giúp rà soát toàn bộ server xem có ai đã out guild ingame mà vẫn còn role trên Discord hay không, hoặc những ai chưa liên kết IGN.",
    commands: [
      { cmd: "/guildconfig", desc: "Cấu hình Guild ID Albion và khu vực máy chủ." },
      { cmd: "/guildcheck", desc: "Tra cứu một nhân vật có thuộc guild hay không." },
      { cmd: "/guildmembers", desc: "Xem danh sách thành viên in-game và Fame." },
      { cmd: "/guildaudit", desc: "Đối soát thành viên in-game với Discord (Officer)." },
      { cmd: "/newmembers", desc: "Liệt kê thành viên mới vào Discord trong khoảng ngày đã chọn." }
    ]
  },
  { 
    title: "⚔️ Massing / CTA", 
    desc: "Quản lý party, setup vũ khí, role cực mượt với hệ thống Lock an toàn.", 
    icon: "⚔️",
    details: "Cơ chế hoạt động: Dành riêng cho các trận ZvZ/CTA. Officer có thể tạo một bảng điểm danh (Massing) với các vai trò cụ thể (Tank, Healer, DPS...). Thành viên chỉ cần bấm nút để chọn vai trò. Hệ thống sử dụng khóa đồng thời (Asyncio Lock) để đảm bảo hàng trăm người bấm cùng lúc vẫn không bị lỗi hay kẹt API.",
    commands: [
      { cmd: "/massing", desc: "Mở bảng điểm danh CTA mới với các template vũ khí." },
      { cmd: "/masstemplatelist", desc: "Xem danh sách các đội hình (template) đã lưu." }
    ]
  },
  { 
    title: "🔮 Siphoned Energy", 
    desc: "Theo dõi thành viên hút siphoned từ guild, cập nhật bảng rank.", 
    icon: "💎",
    details: "Bot nhập log Siphoned để cộng dồn điểm, lưu lịch sử và cập nhật mốc thời gian trong cùng transaction. Upload lại phần log đã nhập không cộng lần hai. Officer có thể cộng/trừ điểm thủ công; các chỉnh sửa được tuần tự hóa với import.",
    commands: [
      { cmd: "/spupdate", desc: "Cập nhật và ghi log điểm Siphoned Energy." },
      { cmd: "/spcheck", desc: "Hiển thị bảng xếp hạng thành viên đóng góp nhiều nhất." },
      { cmd: "/addsp", desc: "Cộng điểm Siphoned thủ công cho thành viên (Officer)." }
    ]
  },
  { 
    title: "🚨 Global Blacklist", 
    desc: "Cơ sở dữ liệu danh sách đen liên minh, cảnh báo ngay khi nộp đơn.", 
    icon: "🚨",
    details: "Danh sách đen được quản lý qua dashboard và dùng để cảnh báo trong luồng Onboarding. Bản bot hiện đang nạp không đăng ký nhóm slash /blacklist; đăng nhập dashboard để tra cứu, admin quản lý các record.",
    commands: []
  },
  { 
    title: "📦 Quản lý Core-Bank", 
    desc: "Nộp Core/Vortex tích điểm tự động.", 
    icon: "📦",
    details: "Cơ chế hoạt động: Bot cung cấp hệ thống kênh chuyên dụng để báo cáo việc nhặt được Power Core hoặc Energy Vortex. Thành viên chỉ cần up hình ảnh, Officer thả reaction là bot tự động cộng điểm tích lũy vào ngân hàng Core của thành viên đó.",
    commands: [
      { cmd: "/coresetup", desc: "Thiết lập kênh làm nơi nộp Core." },
      { cmd: "/coreadd", desc: "Đăng ký emoji để thả reaction xác nhận." },
      { cmd: "/corelist", desc: "Xem bảng giá emoji Core và cấu hình hiện tại." }
    ]
  },
  { 
    title: "🤖 AI Assistant & TTS", 
    desc: "Bot AI giải đáp game và đọc text-to-speech trong Voice.", 
    icon: "🤖",
    details: "Cơ chế hoạt động: Được tích hợp AI (Gemini/Ollama) với kiến thức RAG về cơ chế game Albion. Newbie có thể tag Bot để hỏi mọi thứ về game. Kèm theo đó là hệ thống TTS (Text-to-Speech) - Bot có thể nhảy vào kênh Voice và đọc to tin nhắn chat bằng tiếng Việt siêu mượt.",
    commands: [
      { cmd: "/alo", desc: "Bắt bot đọc tin nhắn text thành giọng nói trong Voice." },
      { cmd: "/alojoin", desc: "Kéo bot vào kênh Voice hiện tại của bạn." },
      { cmd: "/aichat intercept", desc: "Bật/Tắt tính năng AI nói leo vào cuộc trò chuyện." },
      { cmd: "/wiki", desc: "Tra cứu thư viện Wiki của Albion thông qua bot." }
    ]
  },
];

export default function Home() {
  const [entries, setEntries] = useState<BlacklistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState("home");
  const [selectedFeature, setSelectedFeature] = useState<any>(null);
  const { data: session, status } = useSession();

  useEffect(() => {
    let active = true;
    if (status === "loading") {
      setLoading(true);
      return () => { active = false; };
    }
    if (status !== "authenticated") {
      setEntries([]);
      setError("Đăng nhập Discord để xem danh sách đen.");
      setLoading(false);
      return () => { active = false; };
    }

    setLoading(true);
    setError("");
    const fetchBlacklist = async () => {
      try {
        const response = await fetch('/api/blacklist', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(response.status === 401
            ? "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại."
            : "Không thể tải danh sách đen từ dashboard.");
        }
        const data: unknown = await response.json();
        if (!Array.isArray(data)) throw new Error("Dữ liệu danh sách đen không hợp lệ.");
        if (active) setEntries(data);
      } catch (error: unknown) {
        if (active) {
          setError(error instanceof Error ? error.message : "Không thể tải danh sách đen.");
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchBlacklist();
    return () => { active = false; };
  }, [status]);

  const filteredEntries = entries.filter((entry) =>
    entry.ingame_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    entry.discord_id.includes(searchTerm)
  );

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="glass-panel sticky top-0 z-50 border-b-0 border-border rounded-b-2xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-purple-400 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]">
                T
              </div>
              <span className="font-bold text-xl tracking-wide">TNC Bot</span>
            </div>
            <div className="flex gap-6 overflow-x-auto no-scrollbar">
              {[
                { id: 'home', label: 'Giới Thiệu' },
                { id: 'guide', label: 'Hướng Dẫn Cài Đặt' },
                { id: 'blacklist', label: 'Global Blacklist' },
                { id: 'credits', label: 'Đội Ngũ Tác Giả' },
              ].map((tab) => (
                <button 
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`text-sm font-medium transition-colors whitespace-nowrap ${activeTab === tab.id ? 'text-primary' : 'text-text-muted hover:text-text-main'}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Login / User Profile */}
            <div className="flex items-center gap-4 ml-4">
              {session?.user ? (
                <div className="flex items-center gap-3">
                  <img src={session.user.image || ''} alt="Avatar" className="w-8 h-8 rounded-full border border-border" />
                  <span className="text-sm font-semibold hidden md:block">{session.user.name}</span>
                  <button onClick={() => signOut()} className="text-xs text-text-muted hover:text-red-400 transition-colors">Đăng xuất</button>
                </div>
              ) : (
                <button onClick={() => signIn("discord")} className="bg-[#5865F2] hover:bg-[#4752C4] text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 shadow-lg shadow-[#5865F2]/20 whitespace-nowrap">
                  <svg width="16" height="16" viewBox="0 0 127.14 96.36" fill="currentColor">
                    <path d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.31,60,73.31,53s5-12.74,11.43-12.74S96.1,46,96,53,91,65.69,84.69,65.69Z"/>
                  </svg>
                  Login
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {activeTab === "home" ? (
          <div className="space-y-24 animate-fade-in">
            
            {/* Hero Section */}
            <div className="text-center space-y-8 pt-12">
              <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight">
                Quản lý Guild Albion <br/>
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-400">
                  Dễ Dàng Hơn Bao Giờ Hết
                </span>
              </h1>
              <p className="text-lg md:text-xl text-text-muted max-w-2xl mx-auto leading-relaxed">
                TNC Bot là giải pháp toàn diện giúp các Officer tự động hóa quy trình quản lý thành viên, tổ chức Massing, theo dõi Siphoned Energy và cảnh báo Scammer liên minh.
              </p>
              <div className="flex justify-center gap-4 pt-4">
                <Link href="/dashboard" className="bg-primary hover:bg-indigo-500 text-white px-8 py-3 rounded-full font-semibold transition-all shadow-[0_0_20px_rgba(99,102,241,0.4)] hover:shadow-[0_0_30px_rgba(99,102,241,0.6)] hover:-translate-y-1 block">
                  Vào Dashboard Quản Trị (Test)
                </Link>
                <button onClick={() => setActiveTab('guide')} className="glass-panel text-text-main hover:text-white px-8 py-3 rounded-full font-semibold transition-all hover:bg-surface-hover">
                  Xem Hướng Dẫn Cài Đặt
                </button>
              </div>

              {/* Flex Stats Section */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto pt-16 border-t border-border/50 mt-16">
                <div className="flex flex-col items-center p-4">
                  <span className="text-4xl font-extrabold text-white mb-2 tracking-tighter">15+</span>
                  <span className="text-sm text-text-muted uppercase tracking-wider font-semibold">Guilds Tin Dùng</span>
                </div>
                <div className="flex flex-col items-center p-4">
                  <span className="text-4xl font-extrabold text-white mb-2 tracking-tighter">24/7</span>
                  <span className="text-sm text-text-muted uppercase tracking-wider font-semibold">Uptime</span>
                </div>
                <div className="flex flex-col items-center p-4 relative group">
                  <div className="absolute inset-0 bg-primary-glow blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                  <span className="text-4xl font-extrabold text-primary mb-2 tracking-tighter relative z-10">AI</span>
                  <span className="text-sm text-text-muted uppercase tracking-wider font-semibold relative z-10">Tích Hợp Sẵn</span>
                </div>
                <div className="flex flex-col items-center p-4">
                  <span className="text-4xl font-extrabold text-white mb-2 tracking-tighter">500+</span>
                  <span className="text-sm text-text-muted uppercase tracking-wider font-semibold">Scammer Bị Chặn</span>
                </div>
              </div>
            </div>

            {/* Features Section */}
            <div>
              <div className="text-center mb-12">
                <h2 className="text-3xl font-bold">Tính Năng Nổi Bật</h2>
                <p className="text-text-muted mt-2">Chọn những module bạn cần cho Guild của mình</p>
              </div>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {FEATURES.map((feature, i) => (
                  <div 
                    key={i} 
                    onClick={() => setSelectedFeature(feature)}
                    className="glass-panel p-6 rounded-2xl hover:-translate-y-2 transition-transform duration-300 group cursor-pointer relative overflow-hidden flex flex-col"
                  >
                    <div className="absolute top-0 right-0 w-32 h-32 bg-primary-glow rounded-full blur-3xl -mr-16 -mt-16 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <div className="text-4xl mb-4">{feature.icon}</div>
                    <h3 className="text-xl font-bold mb-2 group-hover:text-primary transition-colors">{feature.title}</h3>
                    <p className="text-sm text-text-muted leading-relaxed mb-4">{feature.desc}</p>
                    
                    <div className="mt-auto pt-4 border-t border-border/50">
                      <p className="text-xs font-semibold text-text-muted uppercase mb-2">Các lệnh nổi bật:</p>
                      <div className="flex flex-wrap gap-2">
                        {feature.commands.map((cmd: any, j: number) => (
                          <span key={j} className="text-xs bg-surface border border-border px-2 py-1 rounded text-primary/80">
                            {cmd.cmd}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 flex items-center justify-between">
                      <span className="text-xs font-semibold text-primary">Xem Chi Tiết Lệnh</span>
                      <div className="w-8 h-4 bg-surface rounded-full p-0.5 border border-border">
                        <div className="w-3 h-3 bg-text-muted rounded-full group-hover:bg-primary group-hover:translate-x-4 transition-all"></div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        ) : activeTab === "blacklist" ? (
          <div className="animate-fade-in">
            <div className="flex flex-col md:flex-row items-center justify-between mb-12">
              <div>
                <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400">
                  Global Blacklist
                </h1>
                <p className="mt-2 text-text-muted">
                  Hệ thống cơ sở dữ liệu danh sách đen tự động đồng bộ từ Discord
                </p>
              </div>
              <div className="mt-4 md:mt-0 relative w-full md:w-96">
                <input
                  type="text"
                  placeholder="Tìm kiếm theo Tên Ingame hoặc Discord ID..."
                  className="w-full glass-panel text-text-main placeholder-text-muted rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-primary transition-all duration-300"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            {loading ? (
              <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
              </div>
            ) : error ? (
              <div className="glass-panel p-6 rounded-2xl border-red-900/50 text-center">
                <p className="text-red-400 font-semibold mb-2">⚠️ Đã xảy ra lỗi</p>
                <p className="text-text-muted">{error}</p>
                <p className="text-sm mt-4 text-text-muted">Dữ liệu được tải từ API cùng website sau khi đăng nhập.</p>
                {(status !== "authenticated" || error.startsWith("Phiên đăng nhập")) && (
                  <button onClick={() => signIn("discord")} className="mt-4 bg-[#5865F2] hover:bg-[#4752C4] text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors">
                    Đăng nhập lại bằng Discord
                  </button>
                )}
              </div>
            ) : filteredEntries.length === 0 ? (
              <div className="glass-panel p-12 rounded-2xl text-center border-border">
                <p className="text-xl text-text-muted mb-4">Chưa có ai bị đưa vào danh sách đen.</p>
                <p className="text-sm text-text-muted">Dùng lệnh <code className="bg-surface px-2 py-1 rounded text-primary">/blacklist add</code> trên Discord để thêm Scammer đầu tiên!</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredEntries.map((entry, idx) => (
                  <div
                    key={idx}
                    className="glass-panel rounded-2xl p-6 transition-all duration-300 hover:scale-[1.02] hover:-translate-y-1 hover:border-primary-glow group"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-white group-hover:text-primary transition-colors">
                          {entry.ingame_name}
                        </h3>
                        <p className="text-xs text-text-muted mt-1 break-all">ID: {entry.ingame_id || "N/A"}</p>
                      </div>
                      <span className="bg-red-500/10 text-red-400 text-xs font-medium px-2.5 py-1 rounded-full border border-red-500/20">
                        SCAMMER
                      </span>
                    </div>
                    
                    <div className="space-y-3 mt-6">
                      <div className="flex flex-col">
                        <span className="text-xs text-text-muted uppercase tracking-wider">Discord ID</span>
                        <span className="font-mono text-sm">{entry.discord_id}</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span className="text-xs text-text-muted uppercase tracking-wider">Lý do Blacklist</span>
                        <p className="text-sm text-gray-300 leading-relaxed mt-1 line-clamp-3">
                          {entry.reason}
                        </p>
                      </div>
                    </div>
                    
                    <div className="mt-6 pt-4 border-t border-border flex justify-between items-center text-xs text-text-muted">
                      <span>By: {entry.added_by_discord_id}</span>
                      <span>{new Date(entry.timestamp).toLocaleDateString("vi-VN")}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : activeTab === "guide" ? (
          <div className="animate-fade-in py-12 max-w-4xl mx-auto">
            <div className="text-center mb-12">
              <div className="text-6xl mb-6">📚</div>
              <h2 className="text-4xl font-bold mb-4">Hướng Dẫn Cài Đặt TNC Bot</h2>
              <p className="text-text-muted text-lg">
                Mã nguồn mở tại:{" "}
                <a 
                  href="https://github.com/namdzaixd-cpu/Bot_Albion_TNC" 
                  target="_blank" 
                  rel="noreferrer"
                  className="text-primary hover:underline font-semibold transition-colors"
                >
                  GitHub - Bot_Albion_TNC
                </a>
              </p>
            </div>

            <div className="space-y-6 text-left">
              {/* Bước 1 */}
              <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden group hover:border-primary/50 transition-colors">
                <div className="absolute top-0 left-0 w-2 h-full bg-primary"></div>
                <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                  <span className="bg-primary/20 text-primary w-8 h-8 rounded-full flex items-center justify-center text-sm">1</span>
                  Tải Mã Nguồn & Cài Đặt Môi Trường
                </h3>
                <div className="text-text-muted space-y-4 pl-11">
                  <p>Bot được viết bằng <strong>Python</strong> và giao diện Web dùng <strong>Next.js</strong>. Bạn cần cài đặt Python 3.10+ và Node.js 18+ trên máy chủ.</p>
                  <div className="bg-surface/50 p-4 rounded-lg font-mono text-sm border border-border shadow-inner">
                    <p className="text-green-400 mb-1"># Clone repo về máy</p>
                    <p className="text-gray-300">git clone https://github.com/namdzaixd-cpu/Bot_Albion_TNC.git</p>
                    <p className="text-gray-300 mb-3">cd Bot_Albion_TNC</p>
                    
                    <p className="text-green-400 mb-1"># Cài đặt thư viện Python cho Bot</p>
                    <p className="text-gray-300">pip install -r requirements.txt</p>
                  </div>
                </div>
              </div>

              {/* Bước 2 */}
              <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden group hover:border-purple-500/50 transition-colors">
                <div className="absolute top-0 left-0 w-2 h-full bg-purple-500"></div>
                <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                  <span className="bg-purple-500/20 text-purple-400 w-8 h-8 rounded-full flex items-center justify-center text-sm">2</span>
                  Thiết Lập Token & API
                </h3>
                <div className="text-text-muted space-y-4 pl-11">
                  <p>Tạo file <code className="text-purple-400 bg-surface px-2 py-1 rounded-md text-sm border border-border">.env</code> ở thư mục gốc (hoặc copy từ <code className="text-purple-400 bg-surface px-2 py-1 rounded-md text-sm border border-border">.env.example</code>) và điền các cấu hình:</p>
                  <ul className="list-disc pl-5 space-y-2 text-gray-300">
                    <li>
                      <strong>DISCORD_TOKEN:</strong> Lấy từ <a href="https://discord.com/developers/applications" target="_blank" rel="noreferrer" className="text-primary hover:underline">Discord Developer Portal</a>. 
                      <span className="text-red-400 ml-1 text-sm font-medium">Lưu ý: Bật đủ 3 quyền Privileged Gateway Intents.</span>
                    </li>
                    <li>
                      <strong>GEMINI_API_KEY:</strong> (Tùy chọn) Lấy từ Google AI Studio nếu dùng tính năng Chatbot.
                    </li>
                  </ul>
                  <div className="bg-surface/50 p-4 rounded-lg font-mono text-sm border border-border shadow-inner mt-2">
                    <p className="text-gray-300">DISCORD_TOKEN=<span className="text-purple-300">MTEyMz... (Token bot của bạn)</span></p>
                    <p className="text-gray-300">GEMINI_API_KEY=<span className="text-purple-300">AIzaSy... (API Key của Google)</span></p>
                  </div>
                </div>
              </div>

              {/* Bước 3 */}
              <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden group hover:border-blue-500/50 transition-colors">
                <div className="absolute top-0 left-0 w-2 h-full bg-blue-500"></div>
                <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
                  <span className="bg-blue-500/20 text-blue-400 w-8 h-8 rounded-full flex items-center justify-center text-sm">3</span>
                  Khởi Chạy Bot & API Server
                </h3>
                <div className="text-text-muted space-y-4 pl-11">
                  <p>Chạy file main của bot. Hệ thống sẽ tự động khởi động cả Bot Discord và một Web API cục bộ (cổng 5000) để phục vụ cho Dashboard.</p>
                  <div className="bg-surface/50 p-4 rounded-lg font-mono text-sm border border-border shadow-inner">
                    <p className="text-green-400 mb-1"># Chạy bot (tại thư mục gốc của dự án)</p>
                    <p className="text-gray-300">python bot/main.py</p>
                  </div>
                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 flex items-start gap-3 mt-2">
                    <span className="text-blue-400">💡</span>
                    <p className="text-sm text-blue-200">
                      Bạn sẽ thấy log trên console thông báo Bot đã online và API Server đang lắng nghe trên cổng 5000.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="animate-fade-in text-center py-12 max-w-4xl mx-auto">
            <div className="text-6xl mb-6">🤝</div>
            <h2 className="text-3xl font-bold mb-8">Đội Ngũ Phát Triển</h2>
            <p className="text-text-muted mb-12">Những người đứng sau dự án Bot TNC Manager</p>
            <div className="grid md:grid-cols-3 gap-6 text-left">
              <div className="glass-panel p-6 rounded-2xl hover:border-primary-glow transition-all">
                <div className="w-14 h-14 bg-surface rounded-xl mb-4 flex items-center justify-center text-2xl border border-border shadow-md">👨‍💻</div>
                <h3 className="font-bold text-lg text-primary">N4MDZ4I</h3>
                <p className="text-sm text-text-muted mt-2">Phát triển nền tảng, thiết kế cơ sở dữ liệu và các tính năng cốt lõi (Massing, Siphoned...).</p>
              </div>
              <div className="glass-panel p-6 rounded-2xl hover:border-primary-glow transition-all">
                <div className="w-14 h-14 bg-surface rounded-xl mb-4 flex items-center justify-center text-2xl border border-border shadow-md">🤖</div>
                <h3 className="font-bold text-lg text-primary">Kudo2ten</h3>
                <p className="text-sm text-text-muted mt-2">Chịu trách nhiệm mảng Chat AI, tích hợp mô hình ngôn ngữ và xử lý RAG đa luồng.</p>
              </div>
              <div className="glass-panel p-6 rounded-2xl hover:border-primary-glow transition-all">
                <div className="w-14 h-14 bg-surface rounded-xl mb-4 flex items-center justify-center text-2xl border border-border shadow-md">⚙️</div>
                <h3 className="font-bold text-lg text-primary">Twot</h3>
                <p className="text-sm text-text-muted mt-2">Tối ưu hiệu năng, gỡ lỗi và hoàn thiện hệ thống để bot chạy mượt mà 24/7.</p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Modal */}
      {selectedFeature && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fade-in">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedFeature(null)}></div>
          <div className="relative glass-panel w-full max-w-2xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh] shadow-[0_0_50px_rgba(99,102,241,0.2)]">
            <div className="p-6 border-b border-border/50 flex items-start justify-between bg-surface/50">
              <div className="flex items-center gap-4">
                <div className="text-4xl">{selectedFeature.icon}</div>
                <div>
                  <h3 className="text-2xl font-bold text-white">{selectedFeature.title}</h3>
                  <p className="text-primary text-sm font-medium mt-1">Module Tính Năng</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedFeature(null)}
                className="text-text-muted hover:text-white transition-colors p-2 rounded-lg hover:bg-surface-hover"
              >
                ✕
              </button>
            </div>
            <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
              <div className="mb-8">
                <h4 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <span className="text-primary">⚡</span> Cơ Chế Hoạt Động
                </h4>
                <p className="text-text-muted leading-relaxed text-sm md:text-base">
                  {selectedFeature.details}
                </p>
              </div>
              <div>
                <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span className="text-primary">⌨️</span> Danh Sách Lệnh Chi Tiết
                </h4>
                <div className="space-y-3">
                  {selectedFeature.commands.map((cmd: any, idx: number) => (
                    <div key={idx} className="bg-surface/50 border border-border rounded-xl p-4 flex flex-col md:flex-row md:items-center gap-3 md:gap-6 hover:border-primary/50 transition-colors">
                      <code className="text-primary font-mono text-sm bg-primary/10 px-3 py-1.5 rounded-lg whitespace-nowrap w-fit">
                        {cmd.cmd}
                      </code>
                      <p className="text-sm text-text-muted">{cmd.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-6 border-t border-border/50 bg-surface/30 flex justify-end">
              <button 
                onClick={() => setSelectedFeature(null)}
                className="bg-primary hover:bg-indigo-500 text-white px-6 py-2 rounded-xl font-semibold transition-colors"
              >
                Đã Hiểu
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

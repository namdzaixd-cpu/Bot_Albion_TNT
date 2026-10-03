"use client";

import { useEffect, useRef, useState } from "react";
import { Package, Eye, EyeOff, Settings2, Trash2, Plus } from "lucide-react";
import SearchableSelect, { Option } from "@/components/SearchableSelect";
import { toast } from "react-hot-toast";

export default function CoreBankDashboard() {
  const [channels, setChannels] = useState<Option[]>([]);
  const [showToken, setShowToken] = useState(false);
  const [tokenDraft, setTokenDraft] = useState("");

  const [config, setConfig] = useState({
    core_channel_id: "",
    bank_channel_id: "",
    token_configured: false,
    auto_react: true,
    emoji_map: {} as Record<string, { name: string; value: number; display: string; order: number }>
  });

  const [newEmoji, setNewEmoji] = useState({ key: "", name: "", value: "", display: "", order: "0" });
  const saveQueue = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    fetch('/api/discord-data')
      .then(res => res.json())
      .then(data => {
        if (data.channels) setChannels(data.channels);
      });

    fetch('/api/corebank')
      .then(res => res.json())
      .then(data => {
        if (data && !data.error) {
          setConfig({
            core_channel_id: data.core_channel_id || "",
            bank_channel_id: data.bank_channel_id || "",
            token_configured: data.token_configured === true,
            auto_react: data.auto_react ?? true,
            emoji_map: data.emoji_map || {}
          });
        }
      });
  }, []);

  const queueSave = (patch: Record<string, unknown>) => {
    const save = async () => {
      try {
        const response = await fetch('/api/corebank', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch)
        });
        const payload: unknown = await response.json().catch(() => null);
        const result = payload && typeof payload === 'object' ? payload : {};
        const saved = Reflect.get(result, 'saved') === true;
        const applied = Reflect.get(result, 'applied') === true;
        const error = Reflect.get(result, 'error');

        if (saved && 'unbelievaboat_token' in patch) {
          const configured = Reflect.get(result, 'token_configured') === true;
          const submittedToken = patch.unbelievaboat_token;
          setConfig(previous => ({ ...previous, token_configured: configured }));
          setTokenDraft(previous => previous === submittedToken ? "" : previous);
        }
        if (!response.ok || !applied) {
          toast.error(typeof error === 'string' ? error : "Lỗi lưu cấu hình CoreBank!", { position: 'bottom-right' });
          return;
        }
        toast.success("Đã tự động lưu cấu hình CoreBank!", { position: 'bottom-right' });
      } catch {
        toast.error("Lỗi mạng!", { position: 'bottom-right' });
      }
    };
    saveQueue.current = saveQueue.current.then(save, save);
  };

  const handleChange = (key: 'core_channel_id' | 'bank_channel_id' | 'auto_react', value: string | boolean) => {
    if (key === 'auto_react') {
      if (typeof value !== 'boolean') return;
      setConfig(previous => ({ ...previous, auto_react: value }));
    } else {
      if (typeof value !== 'string') return;
      setConfig(previous => ({ ...previous, [key]: value }));
    }
    queueSave({ [key]: value });
  };

  const handleAddEmoji = () => {
    if (!newEmoji.key || !newEmoji.name || !newEmoji.value) {
      toast.error("Vui lòng nhập đủ ID/Emoji, Tên và Giá trị!");
      return;
    }
    const value = parseInt(newEmoji.value);
    if (isNaN(value) || value <= 0) {
      toast.error("Giá trị không hợp lệ!");
      return;
    }

    const key = newEmoji.key;
    const emoji = {
      name: newEmoji.name,
      value,
      display: newEmoji.display || key,
      order: parseInt(newEmoji.order) || 0
    };
    setConfig(previous => ({
      ...previous,
      emoji_map: { ...previous.emoji_map, [key]: emoji }
    }));
    queueSave({ emoji_operation: 'set', key, value: emoji });
    setNewEmoji({ key: "", name: "", value: "", display: "", order: "0" });
  };

  const handleRemoveEmoji = (key: string) => {
    setConfig(previous => {
      const emojiMap = { ...previous.emoji_map };
      delete emojiMap[key];
      return { ...previous, emoji_map: emojiMap };
    });
    queueSave({ emoji_operation: 'remove', key });
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
          <Package className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Quản Lý Core-Bank</h1>
          <p className="text-text-muted text-sm mt-1">Cấu hình tự động cộng tiền UnbelievaBoat qua hình ảnh Core.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Cấu Hình Chung */}
        <div className="space-y-6">
          <div className="bg-surface border border-border rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="font-medium text-white flex items-center gap-2 border-b border-border pb-3">
              <Settings2 className="w-4 h-4 text-primary" /> Kênh & API
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Kênh Core-Vortex (Nhận ảnh)</label>
                <SearchableSelect
                  options={channels}
                  value={config.core_channel_id}
                  onChange={(val) => handleChange('core_channel_id', val)}
                  placeholder="Chọn kênh nhận ảnh..."
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Kênh Bank (Logs UnbelievaBoat)</label>
                <SearchableSelect
                  options={channels}
                  value={config.bank_channel_id}
                  onChange={(val) => handleChange('bank_channel_id', val)}
                  placeholder="Chọn kênh logs bank..."
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">UnbelievaBoat API Token</label>
                <div className="relative">
                  <input
                    type={showToken ? "text" : "password"}
                    value={tokenDraft}
                    onChange={(event) => setTokenDraft(event.target.value)}
                    onBlur={(event) => {
                      if (event.currentTarget.value) {
                        queueSave({ unbelievaboat_token: event.currentTarget.value });
                      }
                    }}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary pr-10"
                    placeholder={config.token_configured ? "Đã cấu hình — nhập token mới để thay" : "Nhập API Token..."}
                  />
                  {config.token_configured && (
                    <p className="mt-1 text-xs text-green-400">Token đã được cấu hình; để trống sẽ giữ nguyên.</p>
                  )}
                  <button 
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-white"
                  >
                    {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <div>
                  <label className="text-sm font-medium text-white">Tự Động Phân Loại (Auto React)</label>
                  <p className="text-xs text-text-muted">Tự động thả emoji vào ảnh để Officer chấm.</p>
                </div>
                <button
                  onClick={() => handleChange('auto_react', !config.auto_react)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-300 focus:outline-none ${
                    config.auto_react ? 'bg-green-500' : 'bg-surface-hover'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-300 ${
                      config.auto_react ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Danh Sách Emoji Core */}
        <div className="bg-surface border border-border rounded-xl p-5 shadow-sm flex flex-col">
          <h2 className="font-medium text-white flex items-center gap-2 border-b border-border pb-3 mb-4">
            <Package className="w-4 h-4 text-orange-400" /> Bảng Giá Core (Emoji)
          </h2>
          
          <div className="flex-1 overflow-y-auto max-h-64 custom-scrollbar pr-2 space-y-2">
            {Object.entries(config.emoji_map || {}).length > 0 ? (
              Object.entries(config.emoji_map).sort((a,b) => a[1].order - b[1].order).map(([key, info]) => (
                <div key={key} className="flex items-center justify-between bg-background border border-border rounded-lg p-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{info.display}</span>
                    <div>
                      <p className="text-sm font-bold text-white">{info.name}</p>
                      <p className="text-xs text-text-muted">{info.value.toLocaleString()} Silver</p>
                    </div>
                  </div>
                  <button onClick={() => handleRemoveEmoji(key)} className="text-red-400 hover:text-red-300 p-2 bg-red-400/10 rounded-lg">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            ) : (
              <p className="text-sm text-text-muted text-center py-8">Chưa có Core nào được cài đặt.</p>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-border space-y-3">
            <h3 className="text-xs font-semibold text-text-muted uppercase">Thêm Core Mới</h3>
            <div className="grid grid-cols-2 gap-2">
              <input type="text" placeholder="Key (VD: 🟢 hoặc 12345)" className="bg-background border border-border rounded text-sm px-2 py-1" value={newEmoji.key} onChange={e => setNewEmoji({...newEmoji, key: e.target.value})} />
              <input type="text" placeholder="Hiển thị (VD: 🟢 hoặc <:a:123>)" className="bg-background border border-border rounded text-sm px-2 py-1" value={newEmoji.display} onChange={e => setNewEmoji({...newEmoji, display: e.target.value})} />
              <input type="text" placeholder="Tên Core (VD: Xanh lá)" className="bg-background border border-border rounded text-sm px-2 py-1" value={newEmoji.name} onChange={e => setNewEmoji({...newEmoji, name: e.target.value})} />
              <input type="number" placeholder="Giá trị (VD: 100000)" className="bg-background border border-border rounded text-sm px-2 py-1" value={newEmoji.value} onChange={e => setNewEmoji({...newEmoji, value: e.target.value})} />
            </div>
            <button onClick={handleAddEmoji} className="w-full bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 rounded-lg py-2 text-sm font-medium transition-colors flex items-center justify-center gap-2">
              <Plus className="w-4 h-4" /> Thêm Core
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

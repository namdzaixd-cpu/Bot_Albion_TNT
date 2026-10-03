"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, MessageSquare, Zap, Book, Eye } from "lucide-react";
import { toast } from "react-hot-toast";
import MultiSearchableSelect, { Option } from "@/components/MultiSearchableSelect";

export default function AIDashboard() {
  const [channels, setChannels] = useState<Option[]>([]);

  const [config, setConfig] = useState({
    model: "inclusionai/ling-3.0-flash:free",
    intercept_channels: [] as string[],
    autowiki_channels: [] as string[],
    library_channel_ids: [] as string[],
    vision_channels: [] as string[]
  });
  const saveQueue = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    fetch('/api/discord-data')
      .then(res => res.json())
      .then(data => {
        if (data.channels) setChannels(data.channels);
      });

    fetch('/api/ai-config')
      .then(res => res.json())
      .then(data => {
        if (data && !data.error) {
          setConfig({
            model: data.model || "inclusionai/ling-3.0-flash:free",
            intercept_channels: data.intercept_channels || [],
            autowiki_channels: data.autowiki_channels || [],
            library_channel_ids: data.library_channel_ids || [],
            vision_channels: data.vision_channels || []
          });
        }
      });
  }, []);

  const queueSave = (patch: Record<string, unknown>) => {
    const save = async () => {
      try {
        const response = await fetch('/api/ai-config', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch)
        });
        const payload: unknown = await response.json().catch(() => null);
        const result = payload && typeof payload === 'object' ? payload : {};
        const applied = Reflect.get(result, 'applied') === true;
        const error = Reflect.get(result, 'error');
        if (!response.ok || !applied) {
          toast.error(typeof error === 'string' ? error : "Lỗi lưu cấu hình AI!", { position: 'bottom-right' });
          return;
        }
        toast.success("Đã tự động lưu cấu hình AI!", { position: 'bottom-right' });
      } catch {
        toast.error("Lỗi mạng!", { position: 'bottom-right' });
      }
    };
    saveQueue.current = saveQueue.current.then(save, save);
  };

  const handleChange = (
    key: 'intercept_channels' | 'autowiki_channels' | 'library_channel_ids' | 'vision_channels',
    value: string[]
  ) => {
    setConfig(previous => ({ ...previous, [key]: value }));
    queueSave({ [key]: value });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center border border-purple-500/30">
          <Bot className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">AI Config (OpenRouter)</h1>
          <p className="text-text-muted text-sm mt-1">Quản lý kênh phản hồi và mô hình AI của Bot.</p>
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl p-6 shadow-sm space-y-6">
        {/* Model Selection */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-white mb-2">
            <Zap className="w-4 h-4 text-purple-400" /> Mô Hình AI (Model ID)
          </label>
          <p className="text-xs text-text-muted mb-3">Lấy ID model từ OpenRouter, vd: google/gemini-pro, openai/gpt-4o-mini</p>
          <input
            type="text"
            value={config.model}
            onChange={(event) => setConfig(previous => ({ ...previous, model: event.target.value }))}
            onBlur={(event) => queueSave({ model: event.currentTarget.value })}
            className="w-full bg-background border border-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-purple-400 transition-colors"
          />
        </div>

        <div className="border-t border-border pt-6"></div>

        {/* Channels */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-white">
              <MessageSquare className="w-4 h-4 text-blue-400" /> Kênh Tự Động Phản Hồi (Intercept)
            </label>
            <p className="text-xs text-text-muted h-8">Bot sẽ đọc mọi tin nhắn ở đây và tự động nhảy vào chat nếu thấy phù hợp.</p>
            <MultiSearchableSelect
              options={channels}
              values={config.intercept_channels}
              onChange={(vals) => handleChange('intercept_channels', vals)}
              placeholder="Chọn kênh..."
            />
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-white">
              <Book className="w-4 h-4 text-green-400" /> Kênh Auto-Wiki
            </label>
            <p className="text-xs text-text-muted h-8">Bot tự động giải đáp thắc mắc liên quan tới game Albion Online.</p>
            <MultiSearchableSelect
              options={channels}
              values={config.autowiki_channels}
              onChange={(vals) => handleChange('autowiki_channels', vals)}
              placeholder="Chọn kênh..."
            />
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-white">
              <Book className="w-4 h-4 text-orange-400" /> Kênh Kiến Thức (Library)
            </label>
            <p className="text-xs text-text-muted h-8">Khi bật, bot sẽ dùng nội dung của kênh này làm dữ liệu (RAG).</p>
            <MultiSearchableSelect
              options={channels}
              values={config.library_channel_ids}
              onChange={(vals) => handleChange('library_channel_ids', vals)}
              placeholder="Chọn kênh..."
            />
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-white">
              <Eye className="w-4 h-4 text-teal-400" /> Kênh Đọc Ảnh (Vision)
            </label>
            <p className="text-xs text-text-muted h-8">Bot sẽ đọc ảnh trong kênh này và bình luận về bức ảnh.</p>
            <MultiSearchableSelect
              options={channels}
              values={config.vision_channels}
              onChange={(vals) => handleChange('vision_channels', vals)}
              placeholder="Chọn kênh..."
            />
          </div>
        </div>
      </div>
    </div>
  );
}

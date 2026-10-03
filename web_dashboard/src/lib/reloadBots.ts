type ReloadResult =
  | { ok: true }
  | { ok: false; error: string };

/** Server-only: never return or log the shared reload secret. */
export async function reloadBots(): Promise<ReloadResult> {
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret) {
    return { ok: false, error: "Thiếu WEBHOOK_SECRET nên bot chưa tải lại cấu hình." };
  }

  const targets = [
    ["main bot", process.env.BOT_WEBHOOK_URL],
    ["chatbot", process.env.CHATBOT_WEBHOOK_URL],
  ] as const;
  const missing = targets.filter(([, url]) => !url).map(([name]) => name);
  if (missing.length > 0) {
    return {
      ok: false,
      error: `Thiếu webhook của ${missing.join(" và ")} nên bot chưa tải lại cấu hình.`,
    };
  }

  const results = await Promise.all(
    targets.map(async ([name, url]) => {
      try {
        const response = await fetch(url!, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${secret}`,
          },
          body: JSON.stringify({ action: "config_reload" }),
          cache: "no-store",
          signal: AbortSignal.timeout(10_000),
        });
        return response.ok
          ? null
          : `${name} trả về HTTP ${response.status}`;
      } catch {
        return `${name} không thể kết nối`;
      }
    })
  );
  const failures = results.filter((result): result is string => result !== null);
  if (failures.length > 0) {
    return {
      ok: false,
      error: `Đã lưu nhưng bot chưa tải lại cấu hình: ${failures.join("; ")}.`,
    };
  }

  return { ok: true };
}

// Module-level so the queue outlives page unmount/remount within one browser tab.
// shortcut: serializes only this tab; separate tabs/users have no cross-client ordering guarantee.
let tail: Promise<unknown> = Promise.resolve();
let pending = 0;
let version = 0;

export function enqueueSave(save: () => Promise<void>): Promise<void> {
  version += 1;
  pending += 1;
  const run = tail.then(save, save).finally(() => { pending -= 1; });
  tail = run.catch(() => undefined);
  return run;
}

// Wait for every queued save before reading, and re-read if a save was queued during the read.
export async function loadAfterSaves<T>(load: () => Promise<T>): Promise<T> {
  for (;;) {
    while (pending > 0) await tail;
    const startedAt = version;
    const result = await load();
    if (startedAt === version && pending === 0) return result;
  }
}

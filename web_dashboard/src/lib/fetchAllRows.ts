const PAGE_SIZE = 1000; // PostgREST silently caps a single response at its max-rows (1000 by default).

type Page<T> = { data: T[] | null; error: unknown; count: number | null };

// `query` must order by an immutable unique key and select with { count: "exact" }.
// Throws instead of returning a partial list when a page fails or the row count changes between pages;
// it does not detect an insert+delete that leaves the count unchanged.
export async function fetchAllRows<T>(
  query: (from: number, to: number) => PromiseLike<Page<T>>
): Promise<T[]> {
  const rows: T[] = [];
  let total: number | null = null;
  for (;;) {
    const { data, error, count } = await query(rows.length, rows.length + PAGE_SIZE - 1);
    if (error || !data || count === null) throw new Error("page read failed");
    if (total !== null && count !== total) throw new Error("rows changed during read");
    total = count;
    rows.push(...data);
    if (rows.length >= total) break;
    if (data.length === 0) throw new Error("rows changed during read");
  }
  if (rows.length !== total) throw new Error("rows changed during read");
  return rows;
}

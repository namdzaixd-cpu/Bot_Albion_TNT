"""Test memory_store kết nối Supabase thật (không chạy bot).
Kiểm tra: client tạo được, bảng memory/knowledge tồn tại, insert+select thử."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))
from core.config import SUPABASE_URL, SUPABASE_KEY
from core.db import get_client
from core import memory_store as ms

print("=== ENV ===")
print("SUPABASE_URL:", "SET" if SUPABASE_URL else "MISSING")
print("SUPABASE_KEY:", "SET" if SUPABASE_KEY else "MISSING", f"(len={len(SUPABASE_KEY)})")

print("\n=== CLIENT ===")
client = get_client()
if client is None:
    print("❌ Client None -> bot sẽ không query được DB")
    sys.exit(1)
print("✅ Client OK")

print("\n=== TABLE CHECK (select 1 row) ===")
for tbl in ["memory", "knowledge"]:
    try:
        r = client.table(tbl).select("*").limit(1).execute()
        print(f"✅ {tbl}: truy cập OK (rows={len(r.data)})")
    except Exception as e:
        print(f"❌ {tbl}: {e}")

print("\n=== INSERT TEST (memory) ===")
data, err = ms.save_memory("test_user_000", "smoke test tu learning module", kind="fact")
if err:
    print("❌", err)
else:
    print("✅ insert OK:", data)

print("\n=== READ BACK ===")
rows = ms.get_memories("test_user_000", limit=5)
print(f"✅ get_memories trả {len(rows)} rows")
for r in rows[:3]:
    print("  -", r.get("content"))

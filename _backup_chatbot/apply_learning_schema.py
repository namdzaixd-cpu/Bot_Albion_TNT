"""Tao bang memory + knowledge tren Supabase bang connection string (psycopg2).
Chay doc lap, khong dung bot. Doc SQL tu supabase/learning_schema.sql.
"""
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2

SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "supabase", "learning_schema.sql")

def get_dsn():
    # DATABASE_URL la pooler (pgbouncer) -> dung DIRECT_URL cho schema migration
    dsn = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("Thieu DIRECT_URL/DATABASE_URL")
    return dsn

def main():
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = psycopg2.connect(get_dsn())
    conn.autocommit = True
    cur = conn.cursor()
    # Chia tung cau lenh theo ';' de tranh loi comment/extension
    # Nhung file SQL co comment -- nen ta chay ca block 1 lan (psycopg2 hieu duoc)
    try:
        cur.execute(sql)
        print("✅ Tao schema thanh cong (memory + knowledge + pgvector)")
    except Exception as e:
        print("❌ Loi:", e)
        # thu tung cau
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s or s.startswith("--"):
                continue
            try:
                cur.execute(s)
                print("  OK:", s[:60].replace(chr(10), ' '))
            except Exception as e2:
                print("  SKIP:", s[:60].replace(chr(10), ' '), "->", e2)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

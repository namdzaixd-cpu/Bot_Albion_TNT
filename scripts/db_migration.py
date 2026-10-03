"""Create Discord channel/role tables with an explicit PostgreSQL URL."""

import os


SQL = """
CREATE TABLE IF NOT EXISTS discord_channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS discord_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
"""


def run(connect=None) -> int:
    database_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: set DIRECT_URL or DATABASE_URL in the process environment.")
        return 1

    try:
        if connect is None:
            import psycopg

            connect = psycopg.connect
        with connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(SQL)
        print("Discord channel and role tables created or already exist.")
        return 0
    except ImportError:
        print("Error: the psycopg package is required for this migration.")
    except Exception as exc:
        print(f"Discord table migration failed ({type(exc).__name__}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())

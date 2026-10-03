"""Create legacy Discord tables using an explicitly supplied PostgreSQL URL."""

import os


SQL = """
CREATE TABLE IF NOT EXISTS chat_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    channel_name TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS discord_channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    guild_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS discord_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT,
    guild_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
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
        print("Tables created successfully.")
        return 0
    except ImportError:
        print("Error: the psycopg package is required to create tables.")
    except Exception as exc:
        print(f"Table creation failed ({type(exc).__name__}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())

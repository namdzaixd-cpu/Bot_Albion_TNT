"""Apply the repository schema and approved migrations in one transaction."""

import os
from pathlib import Path
from typing import Callable


SCRIPT_DIR = Path(__file__).resolve().parent

class MissingDatabaseDriverError(RuntimeError):
    """The PostgreSQL client library is not installed."""


def _load_driver():
    try:
        import psycopg
    except ImportError as exc:
        raise MissingDatabaseDriverError(
            "The psycopg package is required to apply the schema."
        ) from exc
    return psycopg.connect


def migration_files(scripts_dir: Path = SCRIPT_DIR) -> list[Path]:
    schema = scripts_dir / "schema.sql"
    migrations_dir = scripts_dir / "migrations"
    hardening = scripts_dir / "migration_security.sql"

    required = (schema, hardening)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Required schema input is missing: " + ", ".join(missing)
        )
    if not migrations_dir.is_dir():
        raise FileNotFoundError("Required schema input is missing: migrations/")

    migrations = sorted(migrations_dir.glob("*.sql"), key=lambda path: path.name)
    return [schema, *migrations, hardening]


def apply_migrations(
    database_url: str,
    *,
    scripts_dir: Path = SCRIPT_DIR,
    connect: Callable | None = None,
) -> list[str]:
    files = migration_files(scripts_dir)
    if connect is None:
        connect = _load_driver()

    applied = []
    with connect(database_url) as connection:
        with connection.cursor() as cursor:
            for path in files:
                cursor.execute(path.read_text(encoding="utf-8"))
                applied.append(path.name)
    return applied


def main() -> int:
    database_url = os.getenv("DIRECT_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: set DIRECT_URL or DATABASE_URL in the process environment.")
        return 1

    try:
        applied = apply_migrations(database_url)
    except MissingDatabaseDriverError as exc:
        print(str(exc))
        return 1
    except Exception as exc:
        print(f"Schema application failed ({type(exc).__name__}); the transaction was rolled back.")
        return 1

    for filename in applied:
        print(f"Applied {filename}")
    print("Schema applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check bot DB configuration offline, or query Supabase only with --check-live."""

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))


def _disable_dotenv() -> None:
    try:
        import dotenv

        dotenv.load_dotenv = lambda *args, **kwargs: False
    except ImportError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="Explicitly make a read-only Supabase query using process environment variables.",
    )
    args = parser.parse_args(argv)

    if not args.check_live:
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY"):
            os.environ[name] = ""
    _disable_dotenv()

    from core import db
    from core.config import GUILD_ID, SUPABASE_KEY, SUPABASE_URL, TOKEN

    if not args.check_live:
        if db.get_client() is not None:
            raise AssertionError("DB must remain disabled without explicit live mode")
        assert db.safe_select("guild_config", filters={"guild_id": str(GUILD_ID)}) == (
            None,
            "client_unavailable",
        )
        print("Offline check passed: the DB client is disabled without explicit credentials.")
        return 0

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Live check requires SUPABASE_URL and a Supabase key in the process environment.")
        return 1

    client = db.get_client()
    if client is None:
        print("Supabase client initialization failed.")
        return 1
    try:
        result = client.table("guild_config").select("guild_id").limit(1).execute()
    except Exception as exc:
        print(f"Supabase read failed ({type(exc).__name__}).")
        return 1

    print(
        "Supabase read succeeded; rows=%d; Discord token=%s."
        % (len(result.data or []), "configured" if TOKEN else "missing")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

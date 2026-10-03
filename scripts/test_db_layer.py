"""Exercise the missing-credentials DB behavior without reading .env or using network."""

import asyncio
import os
import sys
from pathlib import Path


for name in (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "DATABASE_URL",
    "DIRECT_URL",
):
    os.environ[name] = ""

try:
    import dotenv

    dotenv.load_dotenv = lambda *args, **kwargs: False
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.core import config_store, db
from bot.core.config import DEFAULT_GUILD_ID


def main() -> int:
    assert db.get_client() is None
    assert db.safe_select("corebank_config", filters={"guild_id": "x"}) == (
        None,
        "client_unavailable",
    )
    assert db.safe_upsert("corebank_config", {"guild_id": "x"}) == "client_unavailable"

    try:
        config_store.get_config(
            "corebank_config",
            "999",
            default={"guild_id": "999", "auto_react": True},
        )
    except db.DBError:
        pass
    else:
        raise AssertionError("get_config must propagate missing-client read failure")

    try:
        config_store.save_config("corebank_config", {"guild_id": "999"})
    except db.DBError:
        pass
    else:
        raise AssertionError("save_config must propagate missing-client write failure")

    async def check_async_boundary():
        response, error = await db.async_execute(
            lambda client: client.table("corebank_config").select("*")
        )
        assert response is None
        assert error == "client_unavailable"

    asyncio.run(check_async_boundary())
    print(f"Missing-credential behavior verified; default guild configured: {bool(DEFAULT_GUILD_ID)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

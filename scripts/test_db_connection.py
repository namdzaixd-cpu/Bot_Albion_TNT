"""Read-only Supabase REST diagnostic; live calls require --check-live."""

import argparse
import json
import os
import urllib.error
import urllib.request


def required_credentials(url: str, key: str) -> tuple[str, str]:
    if not url or not key:
        raise ValueError("SUPABASE_URL and a Supabase key are required.")
    return url.rstrip("/"), key


def _read_table(base_url: str, key: str, table: str, columns: str) -> int:
    request = urllib.request.Request(f"{base_url}/rest/v1/{table}?select={columns}")
    request.add_header("apikey", key)
    request.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    return len(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-live",
        action="store_true",
        help="Explicitly run read-only REST queries with credentials from the process environment.",
    )
    args = parser.parse_args(argv)

    if not args.check_live:
        try:
            required_credentials("", "")
        except ValueError:
            print("Offline check passed: missing Supabase credentials are rejected before any request.")
            return 0
        raise AssertionError("Missing Supabase credentials should have been rejected")

    try:
        base_url, key = required_credentials(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", ""),
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    try:
        metadata_rows = _read_table(base_url, key, "sp_metadata", "id")
        activity_rows = _read_table(base_url, key, "user_activity", "user_id")
        economy_rows = _read_table(base_url, key, "user_economy", "user_id")
    except urllib.error.HTTPError as exc:
        print(f"Supabase REST request failed (HTTP {exc.code}).")
        return 1
    except Exception as exc:
        print(f"Supabase REST request failed ({type(exc).__name__}).")
        return 1

    print(
        "Read-only Supabase REST checks passed: "
        f"sp_metadata={metadata_rows}, user_activity={activity_rows}, user_economy={economy_rows}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

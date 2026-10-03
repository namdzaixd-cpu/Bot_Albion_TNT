"""Initialize SP metadata from an explicitly selected offline legacy snapshot."""

import argparse

from _legacy_snapshot import (
    create_supabase_client,
    read_snapshot_json,
    resolve_snapshot_dir,
)


SOURCE_FILE = "tnc_sp_v32.json"


def import_snapshot(data: dict, client) -> None:
    client.table("sp_metadata").upsert(
        {"id": 1, "last_update": data.get("last_update", "Chưa có dữ liệu")},
        on_conflict="id",
        ignore_duplicates=True,
    ).execute()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legacy-snapshot-dir",
        required=True,
        help="Directory containing an offline export; bot/Storage is protected and rejected.",
    )
    args = parser.parse_args(argv)

    try:
        snapshot_dir = resolve_snapshot_dir(args.legacy_snapshot_dir)
        data = read_snapshot_json(snapshot_dir, SOURCE_FILE)
        client = create_supabase_client()
        import_snapshot(data, client)
    except Exception as exc:
        print(f"SP metadata import failed ({type(exc).__name__}).")
        return 1

    print("Initialized SP metadata from the selected offline snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

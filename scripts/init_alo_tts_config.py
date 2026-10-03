"""Initialize ALO TTS config from an explicitly selected offline snapshot."""

import argparse

from _legacy_snapshot import (
    create_supabase_client,
    read_snapshot_json,
    resolve_snapshot_dir,
)


SOURCE_FILE = "tnc_tts_config_v1.json"


def import_snapshot(data: dict, client) -> None:
    client.table("alo_tts_config").upsert(
        {
            "id": 1,
            "read_name": data.get("read_name", {}),
            "rejoin": data.get("rejoin", {}),
            "afk": data.get("afk", {}),
        },
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
        print(f"ALO TTS config import failed ({type(exc).__name__}).")
        return 1

    print("Initialized ALO TTS config from the selected offline snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

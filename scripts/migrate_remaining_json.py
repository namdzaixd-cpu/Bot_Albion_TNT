"""Import selected files from an explicitly supplied offline legacy snapshot."""

import argparse
from pathlib import Path

from _legacy_snapshot import (
    create_supabase_client,
    read_snapshot_json,
    resolve_snapshot_dir,
)


REMAINING_FILES = (
    "tnc_massing_v1.json",
    "tnc_templates_v1.json",
    "tnc_guildcheck_config.json",
    "tnc_guildcheck_v1.json",
    "tnc_coreconfig_v1.json",
    "tnc_core_credited_v1.json",
    "tnc_library_v1.json",
    "tnc_blacklist_v1.json",
)


def load_snapshot(snapshot_dir: Path) -> dict[str, object]:
    snapshot = {}
    for filename in REMAINING_FILES:
        path = snapshot_dir / filename
        if path.exists():
            snapshot[filename] = read_snapshot_json(snapshot_dir, filename)
    if not snapshot:
        raise FileNotFoundError("No supported JSON files were found in the selected offline snapshot.")
    return snapshot


def import_snapshot(snapshot: dict[str, object], client) -> int:
    for filename, data in snapshot.items():
        client.table("json_storage").upsert(
            {"file_name": filename, "data": data},
            on_conflict="file_name",
            ignore_duplicates=True,
        ).execute()
    return len(snapshot)


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
        snapshot = load_snapshot(snapshot_dir)
        client = create_supabase_client()
        imported = import_snapshot(snapshot, client)
    except Exception as exc:
        print(f"Legacy snapshot import failed ({type(exc).__name__}).")
        return 1

    print(f"Imported {imported} legacy snapshot file(s) without replacing existing rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

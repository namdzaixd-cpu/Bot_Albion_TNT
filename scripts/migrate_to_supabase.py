"""Import structured records from an explicitly supplied offline legacy snapshot."""

import argparse
from pathlib import Path

from _legacy_snapshot import (
    create_supabase_client,
    read_snapshot_json,
    resolve_snapshot_dir,
)


SOURCE_FILES = (
    "tnc_ai_config.json",
    "tnc_lastseen_v1.json",
    "tnc_sp_v32.json",
    "tnc_tts_config_v1.json",
)
CHUNK_SIZE = 1000


def load_snapshot(snapshot_dir: Path) -> dict[str, object]:
    snapshot = {}
    for filename in SOURCE_FILES:
        if (snapshot_dir / filename).exists():
            snapshot[filename] = read_snapshot_json(snapshot_dir, filename)
    if not snapshot:
        raise FileNotFoundError("No supported JSON files were found in the selected offline snapshot.")
    return snapshot


def _upsert_chunks(client, table: str, records: list[dict]) -> None:
    for start in range(0, len(records), CHUNK_SIZE):
        client.table(table).upsert(
            records[start:start + CHUNK_SIZE],
            ignore_duplicates=True,
        ).execute()


def import_snapshot(snapshot: dict[str, object], client) -> int:
    imported = 0

    ai_config = snapshot.get("tnc_ai_config.json")
    if ai_config is not None:
        client.table("ai_config").upsert(
            {
                "guild_id": "default",
                "model": ai_config.get("model", "inclusionai/ling-3.0-flash:free"),
                "available_models": ai_config.get("available_models", []),
                "channel_buffers": ai_config.get("channel_buffers", {}),
                "intercept_channels": ai_config.get("intercept_channels", []),
                "autowiki_channels": ai_config.get("autowiki_channels", []),
            },
            on_conflict="guild_id",
            ignore_duplicates=True,
        ).execute()
        imported += 1

    lastseen = snapshot.get("tnc_lastseen_v1.json")
    if lastseen is not None:
        records = [
            {"user_id": user_id, "last_seen": timestamp}
            for user_id, timestamp in lastseen.items()
        ]
        _upsert_chunks(client, "user_activity", records)
        imported += 1

    sp_data = snapshot.get("tnc_sp_v32.json")
    if sp_data is not None:
        records = [
            {"user_id": user_id, "silver_pieces": int(amount)}
            for user_id, amount in sp_data.get("history", {}).items()
        ]
        _upsert_chunks(client, "user_economy", records)
        imported += 1

    tts_data = snapshot.get("tnc_tts_config_v1.json")
    if tts_data is not None:
        client.table("alo_tts_config").upsert(
            {
                "id": 1,
                "read_name": tts_data.get("read_name", {}),
                "rejoin": tts_data.get("rejoin", {}),
                "afk": tts_data.get("afk", {}),
            },
            on_conflict="id",
            ignore_duplicates=True,
        ).execute()
        imported += 1
    return imported


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

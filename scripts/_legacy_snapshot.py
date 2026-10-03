"""Shared safeguards for explicitly selected, offline legacy JSON snapshots."""

from pathlib import Path
import json
import os


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def resolve_snapshot_dir(value: str | Path | None) -> Path:
    if not value:
        raise ValueError("Pass --legacy-snapshot-dir with an offline snapshot export directory.")

    try:
        snapshot_dir = Path(value).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError("The selected legacy snapshot directory does not exist.") from exc
    if not snapshot_dir.is_dir():
        raise ValueError("The selected legacy snapshot path is not a directory.")

    protected_storage = (repository_root() / "bot" / "Storage").resolve()
    if (
        _is_within(snapshot_dir, protected_storage)
        or _is_within(protected_storage, snapshot_dir)
    ):
        raise ValueError(
            "bot/Storage is protected operational data; select an offline snapshot export outside bot/Storage."
        )
    return snapshot_dir


def read_snapshot_json(snapshot_dir: Path, filename: str):
    snapshot_dir = snapshot_dir.resolve(strict=True)
    source = (snapshot_dir / filename).resolve(strict=True)
    if not _is_within(source, snapshot_dir) or not source.is_file():
        raise ValueError(f"Snapshot source is not a regular file: {filename}")
    return json.loads(source.read_text(encoding="utf-8"))


def create_supabase_client():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the process environment.")

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("The supabase package is required for an explicit legacy snapshot import.") from exc
    return create_client(url, key)

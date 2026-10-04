import sys
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import create_tables
from _legacy_snapshot import read_snapshot_json, resolve_snapshot_dir
from test_api_key import test_api_full_with_instruction as instruction_helper




def test_create_tables_does_not_log_credentials(monkeypatch, capsys):
    connect = mock.Mock(return_value=mock.MagicMock())
    secret_url = "postgresql://test_user:secret-value@db.example.invalid/test"
    monkeypatch.setenv("DIRECT_URL", secret_url)
    monkeypatch.setenv("DATABASE_URL", "")

    assert create_tables.run(connect=connect) == 0
    assert "secret-value" not in capsys.readouterr().out



def test_legacy_snapshot_import_requires_offline_export_directory(tmp_path):
    snapshot_dir = tmp_path / "export"
    snapshot_dir.mkdir()
    outside = tmp_path / "private.json"
    outside.write_text('{"private": true}', encoding="utf-8")
    try:
        (snapshot_dir / "escape.json").symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks are not permitted on this Windows environment")
    with pytest.raises(ValueError, match="regular file"):
        read_snapshot_json(snapshot_dir, "escape.json")

    with pytest.raises(ValueError, match="offline snapshot"):
        resolve_snapshot_dir(ROOT / "bot" / "Storage")
    with pytest.raises(ValueError, match="--legacy-snapshot-dir"):
        resolve_snapshot_dir(None)


def test_instruction_helper_rejects_missing_explicit_file(tmp_path):

    with pytest.raises(SystemExit):
        instruction_helper.main(["--instruction-path", str(tmp_path / "missing.txt")])
    with pytest.raises(ValueError, match="AI_INSTRUCTION_PATH"):
        instruction_helper.load_instruction("")

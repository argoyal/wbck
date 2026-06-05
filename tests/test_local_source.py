import os
import zipfile
from wbck.sources.local import LocalSource


def test_backup_path_creates_zip_in_destination(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "file.txt").write_text("hello")

    backup_dir = tmp_path / "backups" / "test-workspace"
    backup_dir.mkdir(parents=True)

    source = LocalSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["local"],
        "backup_location": "",
        "enabled": 1
    }

    status, note = source.backup_path(path_entry, [".venv"])

    assert status == "success"
    zips = list((tmp_path / "backups" / "test-workspace").glob("notes-*.zip"))
    assert len(zips) == 1


def test_backup_path_override_location(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "file.txt").write_text("hello")

    override_dir = tmp_path / "custom"
    override_dir.mkdir()

    source = LocalSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["local"],
        "backup_location": str(override_dir / "notes.zip"),
        "enabled": 1
    }

    source.backup_path(path_entry, [])
    assert (override_dir / "notes.zip").exists()


def test_restore_path_extracts_and_deletes_source(new_config, tmp_path, monkeypatch):
    from datetime import date
    zip_name = f"notes-{date.today().isoformat()}.zip"

    backup_dir = tmp_path / "backups" / "test-workspace"
    backup_dir.mkdir(parents=True)
    zip_path = backup_dir / zip_name

    with zipfile.ZipFile(str(zip_path), 'w') as zf:
        zf.writestr("notes/hello.txt", "world")

    source = LocalSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["local"],
        "backup_location": "",
        "enabled": 1
    }

    monkeypatch.chdir(str(tmp_path))
    status = source.restore_path(path_entry)

    assert status == "success"
    assert not zip_path.exists()
    restored = tmp_path / "test-workspace" / "notes" / "hello.txt"
    assert restored.exists()

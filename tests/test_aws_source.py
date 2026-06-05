import os
import zipfile
from unittest.mock import patch, MagicMock
from wbck.sources.aws import AwsSource


def test_backup_path_success(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "file.txt").write_text("hello")

    source = AwsSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["s3"],
        "backup_location": "",
        "enabled": 1
    }

    with patch.object(source, "_get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        status, note = source.backup_path(path_entry, [".venv"])

    assert status == "success"
    assert note == ""
    assert mock_s3.upload_file.called


def test_backup_path_default_s3_key(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "file.txt").write_text("hello")

    source = AwsSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["s3"],
        "backup_location": "",
        "enabled": 1
    }

    with patch.object(source, "_get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        source.backup_path(path_entry, [])

    _, _, key = mock_s3.upload_file.call_args[0]
    assert key.startswith("test-workspace/notes-")
    assert key.endswith(".zip")


def test_backup_path_override_location(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "file.txt").write_text("hello")

    source = AwsSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["s3"],
        "backup_location": "custom/notes-backup.zip",
        "enabled": 1
    }

    with patch.object(source, "_get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        source.backup_path(path_entry, [])

    _, _, key = mock_s3.upload_file.call_args[0]
    assert key == "custom/notes-backup.zip"


def test_restore_path_downloads_and_deletes(new_config, tmp_path, monkeypatch):
    source = AwsSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["s3"],
        "backup_location": "",
        "enabled": 1
    }

    # create a fake zip to extract
    from datetime import date
    zip_name = f"notes-{date.today().isoformat()}.zip"
    zip_source = tmp_path / "source_zip" / zip_name
    zip_source.parent.mkdir(parents=True)
    with zipfile.ZipFile(str(zip_source), 'w') as zf:
        zf.writestr("notes/hello.txt", "world")

    def fake_download(bucket, key, local):
        import shutil
        shutil.copy(str(zip_source), local)

    with patch.object(source, "_get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = fake_download
        mock_client.return_value = mock_s3

        work_dir = tmp_path / "work"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)
        status = source.restore_path(path_entry)

    assert status == "success"
    assert mock_s3.delete_object.called
    delete_args = mock_s3.delete_object.call_args[1]
    assert delete_args["Bucket"] == "my-bucket"

    # Verify extracted file exists at the expected location
    # The file is extracted to workspace_path / workspace_name (which is tmp_path)
    extracted_file = tmp_path / "test-workspace" / "notes" / "hello.txt"
    assert extracted_file.exists()
    assert extracted_file.read_text() == "world"

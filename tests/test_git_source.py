import subprocess
from unittest.mock import patch, MagicMock
from wbck.sources.git import GitSource


def test_backup_path_clean_repo(new_config, tmp_path):
    (tmp_path / "test-workspace" / "notes").mkdir(parents=True)
    source = GitSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["git"],
        "backup_location": "git@github.com:user/notes.git",
        "enabled": 1
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        status, note = source.backup_path(path_entry, [])

    assert status == "success"
    assert note == ""


def test_backup_path_dirty_repo_continue(new_config, tmp_path):
    (tmp_path / "test-workspace" / "notes").mkdir(parents=True)
    source = GitSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["git"],
        "backup_location": "git@github.com:user/notes.git",
        "enabled": 1
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M somefile.py\n", returncode=0)
        with patch("wbck.sources.git._prompt_with_timeout", return_value="c"):
            status, note = source.backup_path(path_entry, [])

    assert status == "skipped"
    assert "uncommitted" in note


def test_backup_path_dirty_repo_timeout(new_config, tmp_path):
    (tmp_path / "test-workspace" / "notes").mkdir(parents=True)
    source = GitSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["git"],
        "backup_location": "git@github.com:user/notes.git",
        "enabled": 1
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M somefile.py\n", returncode=0)
        with patch("wbck.sources.git._prompt_with_timeout", return_value=None):
            status, note = source.backup_path(path_entry, [])

    assert status == "skipped"


def test_restore_path_clones_when_missing(new_config, tmp_path):
    source = GitSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["git"],
        "backup_location": "git@github.com:user/notes.git",
        "enabled": 1
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        source.restore_path(path_entry)

    call_args = mock_run.call_args_list[0][0][0]
    assert "clone" in call_args
    assert "git@github.com:user/notes.git" in call_args


def test_restore_path_pulls_when_exists(new_config, tmp_path):
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    source = GitSource(new_config)
    path_entry = {
        "folder_name": "notes",
        "folder_path": "notes",
        "backup_source": ["git"],
        "backup_location": "git@github.com:user/notes.git",
        "enabled": 1
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        source.restore_path(path_entry)

    call_args = mock_run.call_args_list[0][0][0]
    assert "pull" in call_args

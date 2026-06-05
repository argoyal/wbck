import subprocess
from unittest.mock import patch, MagicMock
from wbck.sources.git import GitSource, _is_binary


_GIT_PATH_ENTRY = {
    "folder_name": "notes",
    "folder_path": "notes",
    "backup_source": ["git"],
    "backup_location": "git@github.com:user/notes.git",
    "enabled": 1
}


def test_backup_path_clean_repo(new_config, tmp_path):
    (tmp_path / "test-workspace" / "notes").mkdir(parents=True)
    source = GitSource(new_config)

    def mock_side_effect(cmd, **kwargs):
        # rev-list --count should return "0" for no unpushed commits
        if "rev-list" in cmd and "--count" in cmd:
            return MagicMock(stdout="0", returncode=0)
        return MagicMock(stdout="", returncode=0)

    with patch("subprocess.run", side_effect=mock_side_effect):
        status, note = source.backup_path(_GIT_PATH_ENTRY, [])

    assert status == "success"
    assert note == ""


def test_backup_path_dirty_code_files_dumped(new_config, tmp_path):
    """Dirty repo with only code (text) files → auto-dump to branch, return success."""
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "somefile.py").write_text("print('hello')")
    source = GitSource(new_config)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M somefile.py\n", returncode=0)
        status, note = source.backup_path(_GIT_PATH_ENTRY, [])

    assert status == "success"
    assert "pushed to local-dump-" in note

    # Verify git commands: reset → add → commit → branch → reset HEAD~1 → push
    cmds = [call[0][0] for call in mock_run.call_args_list]
    assert cmds[0] == ["git", "-C", str(notes_dir), "status", "--porcelain"]
    assert cmds[1][:3] == ["git", "-C", str(notes_dir)] and cmds[1][3] == "reset"
    assert "add" in cmds[2]
    assert "commit" in cmds[3]
    assert "branch" in cmds[4]
    assert cmds[5] == ["git", "-C", str(notes_dir), "reset", "HEAD~1"]
    assert "push" in cmds[6]


def test_backup_path_dirty_binary_files_prompt(new_config, tmp_path):
    """Dirty repo with only binary files → prompt user, return skipped on continue."""
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "data.bin").write_bytes(b"\x00\x01\x02binary")
    source = GitSource(new_config)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M data.bin\n", returncode=0)
        with patch("wbck.sources.git._prompt_with_timeout", return_value="c"):
            status, note = source.backup_path(_GIT_PATH_ENTRY, [])

    assert status == "skipped"
    assert "non-code" in note


def test_backup_path_mixed_dumps_code_prompts_binary(new_config, tmp_path):
    """Dirty repo with code + binary → dump code, prompt for binary, return skipped."""
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "app.py").write_text("import os")
    (notes_dir / "model.pkl").write_bytes(b"\x00\x80pickle")
    source = GitSource(new_config)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=" M app.py\n M model.pkl\n", returncode=0
        )
        with patch("wbck.sources.git._prompt_with_timeout", return_value="c"):
            status, note = source.backup_path(_GIT_PATH_ENTRY, [])

    assert status == "skipped"
    assert "local-dump-" in note
    assert "non-code" in note


def test_backup_path_dirty_code_timeout(new_config, tmp_path):
    """Only code files + timeout → still succeeds (code is dumped, no binary to block on)."""
    notes_dir = tmp_path / "test-workspace" / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "somefile.py").write_text("print('hello')")
    source = GitSource(new_config)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M somefile.py\n", returncode=0)
        status, note = source.backup_path(_GIT_PATH_ENTRY, [])

    assert status == "success"
    assert "local-dump-" in note


def test_is_binary_detects_null_bytes(tmp_path):
    text_file = tmp_path / "code.py"
    text_file.write_text("print('hello')")
    assert not _is_binary(str(text_file))

    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x89PNG\r\n\x00\x1a")
    assert _is_binary(str(bin_file))


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

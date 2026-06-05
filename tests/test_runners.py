import pytest
from unittest.mock import patch, MagicMock
from wbck.runners import backup_data, restore_data


@pytest.fixture
def config_path(tmp_path, new_config):
    import json
    p = tmp_path / "config.json"
    p.write_text(json.dumps(new_config))
    return str(p)


def test_backup_data_calls_backup_path_per_entry(config_path, new_config):
    mock_handler = MagicMock()
    mock_handler.backup_path.return_value = ("success", "")

    with patch("wbck.runners.AwsSource", return_value=mock_handler), \
         patch("wbck.runners.LocalSource", return_value=mock_handler), \
         patch("wbck.runners.GitSource", return_value=mock_handler), \
         patch("wbck.runners.open_log", return_value=(MagicMock(), "/tmp/test.log")), \
         patch("wbck.runners.write_log"), \
         patch("wbck.runners.print_summary"):
        backup_data(config_path)

    assert mock_handler.backup_path.called


def test_backup_data_skips_disabled_paths(tmp_path):
    import json
    config = {
        "name": "ws",
        "enabled": 1,
        "workspace_path": str(tmp_path),
        "paths_to_include": [
            {
                "folder_name": "notes",
                "folder_path": "notes",
                "backup_source": ["s3"],
                "backup_location": "",
                "enabled": 0
            }
        ],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "bucket", "aws_key": "k", "aws_secret": "s", "aws_profile": ""},
            "local": {"root_path": ""},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    mock_handler = MagicMock()

    with patch("wbck.runners.AwsSource", return_value=mock_handler), \
         patch("wbck.runners.open_log", return_value=(MagicMock(), "/tmp/test.log")), \
         patch("wbck.runners.write_log"), \
         patch("wbck.runners.print_summary"):
        backup_data(str(p))

    assert not mock_handler.backup_path.called


def test_restore_data_skips_disabled_workspace(tmp_path, capsys):
    import json
    config = {
        "name": "ws",
        "enabled": 0,
        "workspace_path": str(tmp_path),
        "paths_to_include": [],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "", "aws_key": "", "aws_secret": "", "aws_profile": ""},
            "local": {"root_path": ""},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    restore_data(str(p))
    captured = capsys.readouterr()
    assert "disabled" in captured.out.lower() or "skipping" in captured.out.lower()


def test_restore_data_force_calls_restore_archive(tmp_path):
    import json
    config = {
        "name": "ws",
        "enabled": 0,
        "workspace_path": str(tmp_path),
        "paths_to_include": [],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "b", "aws_key": "k", "aws_secret": "s", "aws_profile": ""},
            "local": {"root_path": ""},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    mock_handler = MagicMock()

    with patch("wbck.runners.AwsSource", return_value=mock_handler), \
         patch("wbck.runners.LocalSource", return_value=mock_handler), \
         patch("builtins.input", return_value="1"):
        restore_data(str(p), force=True)

    assert mock_handler.restore_archive_data.call_count == 1


def test_backup_disabled_workspace_prompts_user(tmp_path):
    import json
    config = {
        "name": "ws",
        "enabled": 0,
        "workspace_path": str(tmp_path),
        "paths_to_include": [],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "b", "aws_key": "k", "aws_secret": "s", "aws_profile": ""},
            "local": {"root_path": "/tmp/backups"},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    mock_handler = MagicMock()

    with patch("wbck.runners.AwsSource", return_value=mock_handler), \
         patch("wbck.runners.LocalSource", return_value=mock_handler), \
         patch("builtins.input", return_value="2") as mock_input:
        backup_data(str(p))

    mock_input.assert_called_once()
    assert mock_handler.archive_data.call_count == 1


def test_backup_disabled_workspace_single_source_auto_selects(tmp_path):
    import json
    config = {
        "name": "ws",
        "enabled": 0,
        "workspace_path": str(tmp_path),
        "paths_to_include": [],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "b", "aws_key": "k", "aws_secret": "s", "aws_profile": ""},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    mock_handler = MagicMock()

    with patch("wbck.runners.AwsSource", return_value=mock_handler), \
         patch("builtins.input") as mock_input:
        backup_data(str(p))

    mock_input.assert_not_called()
    assert mock_handler.archive_data.call_count == 1


def test_backup_disabled_workspace_invalid_selection_exits(tmp_path):
    import json
    config = {
        "name": "ws",
        "enabled": 0,
        "workspace_path": str(tmp_path),
        "paths_to_include": [],
        "paths_to_exclude": [],
        "source_credentials": {
            "s3": {"root_path": "b", "aws_key": "k", "aws_secret": "s", "aws_profile": ""},
            "local": {"root_path": "/tmp/backups"},
            "git": {"auth_method": "ssh"}
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))

    with patch("wbck.runners.AwsSource"), \
         patch("wbck.runners.LocalSource"), \
         patch("builtins.input", return_value="bad"):
        with pytest.raises(SystemExit):
            backup_data(str(p))

import pytest


@pytest.fixture
def new_config(tmp_path):
    """A minimal valid config in the new paths_to_include format."""
    return {
        "name": "test-workspace",
        "enabled": 1,
        "workspace_path": str(tmp_path),
        "paths_to_include": [
            {
                "folder_name": "notes",
                "folder_path": "notes",
                "backup_source": ["s3"],
                "backup_location": "",
                "enabled": 1
            }
        ],
        "paths_to_exclude": [".venv", "node_modules"],
        "source_credentials": {
            "s3": {
                "root_path": "my-bucket",
                "aws_key": "key",
                "aws_secret": "secret",
                "aws_profile": ""
            },
            "local": {
                "root_path": str(tmp_path / "backups")
            },
            "git": {
                "auth_method": "ssh"
            }
        }
    }

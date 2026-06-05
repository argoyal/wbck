# Config Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify `repositories` and `folders_to_maintain` into a single `paths_to_include` list where each path declares its own backup source(s), replace `source_settings` with `source_credentials`, and introduce a path-centric backup/restore runner with interactive git handling and per-run log/summary output.

**Architecture:** Path-centric loop in the runner — iterate `paths_to_include`, dispatch each `(path, source)` pair to the appropriate source handler. Source handlers implement `backup_path(path_entry, paths_to_exclude)` and `restore_path(path_entry)`. Git source handler owns interactive pause logic internally and returns a status string. Logging and tabular summary are built from accumulated results after the loop completes.

**Tech Stack:** Python 3.8+, boto3 (S3), subprocess (git), zipfile, select (stdin timeout), pytest (tests)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `wbck/config_template.json` | Rewrite | New config structure |
| `wbck/utils.py` | Modify | `zipdir` dir exclusion, `open_log`, `write_log`, `print_summary` |
| `wbck/sources/base.py` | Modify | New `__init__`, `_resolve_path`, `_make_path_zip`, abstract `backup_path`/`restore_path` |
| `wbck/sources/git.py` | Create | `GitSource` — interactive backup, clone/pull restore |
| `wbck/sources/aws.py` | Modify | Read from `source_credentials`, add `backup_path`/`restore_path` |
| `wbck/sources/local.py` | Modify | Read from `source_credentials`, add `backup_path`/`restore_path` |
| `wbck/sources/__init__.py` | Modify | Export `GitSource` |
| `wbck/runners.py` | Modify | Path-centric `backup_data`, `restore_data` |
| `tests/conftest.py` | Create | Shared fixtures |
| `tests/test_utils.py` | Create | Tests for log/summary/zipdir |
| `tests/test_git_source.py` | Create | Tests for `GitSource` |
| `tests/test_aws_source.py` | Create | Tests for `AwsSource` path methods |
| `tests/test_local_source.py` | Create | Tests for `LocalSource` path methods |
| `tests/test_runners.py` | Create | Tests for runner path-centric loop |

---

## Task 1: Update config_template.json

**Files:**
- Modify: `wbck/config_template.json`

- [ ] **Step 1: Rewrite the template**

Replace the entire file with:

```json
{
	"name": "",
	"enabled": 1,
	"workspace_path": "",
	"paths_to_include": [
		{
			"folder_name": "workspace-backup",
			"folder_path": "codes/internal/workspace-backup",
			"backup_source": ["git"],
			"backup_location": "git@github.com:argoyal/workspace-backup.git",
			"enabled": 1
		}
	],
	"paths_to_exclude": [".venv", "node_modules", "build", "dist"],
	"source_credentials": {
		"s3": {
			"root_path": "",
			"aws_key": "",
			"aws_secret": "",
			"aws_profile": ""
		},
		"local": {
			"root_path": ""
		},
		"git": {
			"auth_method": "ssh"
		}
	}
}
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('wbck/config_template.json')); print('valid')"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add wbck/config_template.json
git commit -m "feat: rewrite config template to paths_to_include structure"
```

---

## Task 2: Extend utils.py — directory exclusion + log/summary

**Files:**
- Modify: `wbck/utils.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Install pytest if not present**

```bash
pip3 install pytest
```

- [ ] **Step 2: Write the failing tests**

Create `tests/__init__.py` (empty) and `tests/test_utils.py`:

```python
import zipfile
import os
from wbck.utils import zipdir, open_log, write_log, print_summary


def test_zipdir_excludes_directories(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr")
    (tmp_path / "notes.txt").write_text("hello")

    zip_path = str(tmp_path / "test.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zipdir(str(tmp_path), zf, ignore=[".venv"])

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    assert not any(".venv" in n for n in names)
    assert any("notes.txt" in n for n in names)


def test_zipdir_excludes_files(tmp_path):
    (tmp_path / "secret.key").write_text("abc")
    (tmp_path / "notes.txt").write_text("hello")

    zip_path = str(tmp_path / "test.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zipdir(str(tmp_path), zf, ignore=["secret.key"])

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    assert not any("secret.key" in n for n in names)
    assert any("notes.txt" in n for n in names)


def test_write_log(tmp_path):
    log_path = str(tmp_path / "test.log")
    with open(log_path, 'w') as fh:
        write_log(fh, "notes", "s3", "SUCCESS", "")
        write_log(fh, "configs", "local", "FAILED", "Permission denied")

    content = open(log_path).read()
    assert "[notes] [s3] SUCCESS" in content
    assert "[configs] [local] FAILED — Permission denied" in content


def test_print_summary_omits_success_rows(capsys):
    results = [
        ("notes", "s3", "success", ""),
        ("configs", "local", "failed", "Permission denied"),
        ("repo", "git", "skipped", "uncommitted changes"),
    ]
    print_summary(results, "my-workspace", "/tmp/test.log")
    captured = capsys.readouterr()
    assert "configs" in captured.out
    assert "repo" in captured.out
    assert "notes" not in captured.out


def test_print_summary_counts(capsys):
    results = [
        ("a", "s3", "success", ""),
        ("b", "local", "failed", "err"),
        ("c", "git", "skipped", "dirty"),
    ]
    print_summary(results, "ws", "/tmp/test.log")
    captured = capsys.readouterr()
    assert "3 paths" in captured.out
    assert "1 failed" in captured.out
    assert "1 skipped" in captured.out
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/arpitgoyal/workspace-backup && python3 -m pytest tests/test_utils.py -v 2>&1 | head -30
```

Expected: failures about missing `open_log`, `write_log`, `print_summary`, and `zipdir` signature mismatch.

- [ ] **Step 4: Update utils.py**

Replace the entire file:

```python
import os
import zipfile
from datetime import datetime


def zipdir(path, ziph, ignore=[]):
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ignore]
        for file in files:
            if file in ignore:
                continue
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(
                    os.path.join(root, file),
                    os.path.join(path, '..')
                )
            )


def open_log(workspace_name):
    """Opens a new log file in /tmp, returns (file_handle, path)."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"/tmp/wbck-{workspace_name}-{timestamp}.log"
    return open(path, 'w'), path


def write_log(fh, folder_name, source, status, note=""):
    """Appends one line to the open log file handle."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{folder_name}] [{source}] {status}"
    if note:
        line += f" — {note}"
    fh.write(line + "\n")
    fh.flush()


def print_summary(results, workspace_name, log_path):
    """Prints terminal summary table (FAILED/SKIPPED only) and log path."""
    non_success = [(f, s, st, n) for f, s, st, n in results if st != "success"]

    total = len(results)
    failed = sum(1 for _, _, st, _ in results if st == "failed")
    skipped = sum(1 for _, _, st, _ in results if st == "skipped")

    print(f"\nBACKUP SUMMARY — {workspace_name}")
    print("─" * 57)

    if non_success:
        print(f" {'Folder':<20} {'Source':<8} {'Status':<9} Note")
        print("─" * 57)
        for folder, source, status, note in non_success:
            print(f" {folder:<20} {source:<8} {status.upper():<9} {note}")
        print("─" * 57)

    parts = [f"{total} paths processed"]
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if not failed and not skipped:
        parts.append("all succeeded")

    print(" · ".join(parts))
    print(f"\nFull log: {log_path}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_utils.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add wbck/utils.py tests/__init__.py tests/test_utils.py
git commit -m "feat: extend zipdir with dir exclusion, add log/summary utilities"
```

---

## Task 3: Update base.py — new init, path helpers, abstract methods

**Files:**
- Modify: `wbck/sources/base.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write conftest.py with shared config fixture**

Create `tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Update base.py**

Replace the full file:

```python
import os
import shutil
import zipfile
from datetime import datetime

from ..utils import zipdir


class BaseSource(object):
    """
    Base class for all backup/restore sources.
    Workspace-level archival methods (archive_data, restore_archive_data) are
    preserved here for the enabled=0 archival flow.
    Path-level backup_path / restore_path are implemented by each subclass.
    """

    def __init__(self, config_data):
        self.config_data = config_data
        self.source_credentials = config_data.get("source_credentials", {})
        self.paths_to_exclude = config_data.get("paths_to_exclude", [])

        self.workspace_name = config_data["name"]
        self.workspace_path = (
            os.getenv("HOME")
            if not config_data["workspace_path"]
            else config_data["workspace_path"]
        )

        _today = datetime.now().date().isoformat()
        self.zip_name = "{}-{}.zip".format(self.workspace_name, _today)
        self.archive_zip_name = "{}-archive-{}.zip".format(self.workspace_name, _today)
        self.tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')

    # ------------------------------------------------------------------ #
    # Path-level interface (implemented by subclasses)
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """
        Back up a single path entry.
        Returns (status, note) where status is 'success' | 'skipped' | 'failed'.
        """
        raise NotImplementedError()

    def restore_path(self, path_entry):
        """Restore a single path entry. Returns status string."""
        raise NotImplementedError()

    # ------------------------------------------------------------------ #
    # Path-level helpers
    # ------------------------------------------------------------------ #

    def _resolve_path(self, path_entry):
        """Returns the absolute on-disk path for a path_entry."""
        return os.path.join(
            self.workspace_path, self.workspace_name, path_entry["folder_path"]
        )

    def _make_path_zip(self, path_entry, paths_to_exclude):
        """
        Compresses path_entry's folder into a local zip file.
        Returns the local zip filename (in cwd).
        """
        resolved = self._resolve_path(path_entry)
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}.zip".format(path_entry["folder_name"], date)

        zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(resolved, zipf, ignore=paths_to_exclude)
        zipf.close()
        return zip_name

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow — unchanged)
    # ------------------------------------------------------------------ #

    def backup_data(self):
        raise NotImplementedError()

    def archive_data(self):
        raise NotImplementedError()

    def restore_data(self):
        raise NotImplementedError()

    def restore_archive_data(self):
        raise NotImplementedError()

    def perform_cleanup(self):
        os.remove(self.zip_name)
        shutil.rmtree(self.tmp_path)

    def perform_archive_cleanup(self):
        os.remove(self.archive_zip_name)

    def generate_compressed_data(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path)
        if not os.path.exists(self.tmp_path):
            os.system("mkdir -p {}".format(self.tmp_path))

        folders = self.config_data.get("source_settings", {}).get("folders_to_maintain", [])
        for folder in folders:
            src_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            dst_path = os.path.join(self.tmp_path, folder)
            if os.path.exists(dst_path):
                continue
            print(f"Copying {src_path} to tmp location")
            shutil.copytree(src_path, dst_path)

        print(f"Generating zip file {self.zip_name}")
        zipf = zipfile.ZipFile(self.zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(self.tmp_path, zipf, ignore=self.paths_to_exclude)
        zipf.close()

    def generate_full_compressed_data(self):
        workspace_dir = os.path.join(self.workspace_path, self.workspace_name)
        print(f"Generating full archive zip {self.archive_zip_name}")
        zipf = zipfile.ZipFile(self.archive_zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(workspace_dir, zipf, ignore=self.paths_to_exclude)
        zipf.close()

    def extract_from_archive_data(self):
        with zipfile.ZipFile(self.archive_zip_name, 'r') as zip_ref:
            zip_ref.extractall(self.workspace_path)

    def extract_from_compressed_data(self):
        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(self.workspace_path, self.workspace_name))

        folders = self.config_data.get("source_settings", {}).get("folders_to_maintain", [])
        for folder in folders:
            tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')
            dst_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            src_path = os.path.join(tmp_path, folder)

            if not os.path.exists(src_path):
                os.system("mkdir -p {}".format(src_path))
            if os.path.exists(dst_path):
                continue
            shutil.copytree(src_path, dst_path)
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "from wbck.sources.base import BaseSource; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add wbck/sources/base.py tests/conftest.py
git commit -m "feat: update BaseSource with new init, path helpers, and abstract path methods"
```

---

## Task 4: Create sources/git.py — GitSource

**Files:**
- Create: `wbck/sources/git.py`
- Create: `tests/test_git_source.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_git_source.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_git_source.py -v 2>&1 | head -20
```

Expected: ImportError — `wbck.sources.git` not found.

- [ ] **Step 3: Create wbck/sources/git.py**

```python
import os
import select
import subprocess
import sys

from .base import BaseSource


def _prompt_with_timeout(seconds):
    """
    Waits up to `seconds` for a single keystroke on stdin.
    Returns the lowercase first character, or None on timeout.
    """
    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if ready:
        line = sys.stdin.readline().strip().lower()
        if line:
            return line[0]
    return None


class GitSource(BaseSource):

    def backup_path(self, path_entry, paths_to_exclude):
        """
        Checks if the repo is clean. If dirty, prompts user to retry or continue.
        Auto-continues after 60 seconds. Returns ('success'|'skipped', note).
        Git backup is considered done when the repo is clean (remote has latest).
        """
        resolved = self._resolve_path(path_entry)

        while True:
            result = subprocess.run(
                ["git", "-C", resolved, "status", "--porcelain"],
                capture_output=True,
                text=True
            )
            if not result.stdout.strip():
                return "success", ""

            print(
                f"\n[{path_entry['folder_name']}] has uncommitted changes. "
                "[R]etry / [C]ontinue (auto-continue in 60s): ",
                end="",
                flush=True
            )
            choice = _prompt_with_timeout(60)

            if choice == "r":
                continue
            return "skipped", "uncommitted changes"

    def restore_path(self, path_entry):
        """
        Clones the repo if the path doesn't exist locally, otherwise pulls.
        No post-restore deletion (git remote is the source of truth).
        """
        resolved = self._resolve_path(path_entry)
        repo_url = path_entry["backup_location"]

        if os.path.exists(resolved):
            print(f"Pulling {repo_url} in {resolved}")
            subprocess.run(["git", "-C", resolved, "pull"], check=True)
        else:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            print(f"Cloning {repo_url} to {resolved}")
            subprocess.run(["git", "clone", repo_url, resolved], check=True)

        return "success"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_git_source.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add wbck/sources/git.py tests/test_git_source.py
git commit -m "feat: add GitSource with interactive backup pause and clone/pull restore"
```

---

## Task 5: Update aws.py — new init + backup_path/restore_path

**Files:**
- Modify: `wbck/sources/aws.py`
- Create: `tests/test_aws_source.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_aws_source.py`:

```python
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


def test_restore_path_downloads_and_deletes(new_config, tmp_path):
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
    zip_path = tmp_path / zip_name
    with zipfile.ZipFile(str(zip_path), 'w') as zf:
        zf.writestr("notes/hello.txt", "world")

    def fake_download(bucket, key, local):
        import shutil
        shutil.copy(str(zip_path), local)

    with patch.object(source, "_get_s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = fake_download
        mock_client.return_value = mock_s3

        import os
        os.chdir(str(tmp_path))
        status = source.restore_path(path_entry)

    assert status == "success"
    assert mock_s3.delete_object.called
    delete_args = mock_s3.delete_object.call_args[1]
    assert delete_args["Bucket"] == "my-bucket"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_aws_source.py -v 2>&1 | head -30
```

Expected: failures (AwsSource reads `source_settings` which no longer exists in new config).

- [ ] **Step 3: Rewrite aws.py**

```python
import os
import boto3
from datetime import datetime

from .base import BaseSource


class AwsSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        s3_creds = self.source_credentials.get("s3", {})
        self.AWS_KEY = s3_creds.get("aws_key", "")
        self.AWS_SECRET = s3_creds.get("aws_secret", "")
        self.AWS_PROFILE = s3_creds.get("aws_profile", "")
        self.BUCKET_NAME = s3_creds.get("root_path", "")

        # workspace-level archival keys (enabled=0 flow)
        self.s3_key = "{}/{}".format(self.workspace_name, self.zip_name)
        self.archive_s3_key = "{}/{}".format(self.workspace_name, self.archive_zip_name)

    def _get_s3_client(self):
        if self.AWS_PROFILE:
            return boto3.Session(profile_name=self.AWS_PROFILE).client('s3')
        if self.AWS_KEY and self.AWS_SECRET:
            return boto3.client(
                's3',
                aws_access_key_id=self.AWS_KEY,
                aws_secret_access_key=self.AWS_SECRET
            )
        raise ValueError(
            "S3 configuration requires either 'aws_profile' or both 'aws_key' and 'aws_secret'."
        )

    def _s3_key_for_path(self, path_entry):
        """Returns the S3 key to use: backup_location override or generated default."""
        if path_entry.get("backup_location"):
            return path_entry["backup_location"]
        date = datetime.now().date().isoformat()
        return "{}/{}-{}.zip".format(self.workspace_name, path_entry["folder_name"], date)

    # ------------------------------------------------------------------ #
    # Path-level methods
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """Zips the path and uploads to S3. Returns ('success'|'failed', note)."""
        zip_name = self._make_path_zip(path_entry, paths_to_exclude)
        key = self._s3_key_for_path(path_entry)

        print("======================> Uploading {} to s3://{}/{}".format(
            zip_name, self.BUCKET_NAME, key))

        try:
            s3 = self._get_s3_client()
            s3.upload_file(zip_name, self.BUCKET_NAME, key)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        return "success", ""

    def restore_path(self, path_entry):
        """Downloads zip from S3, extracts it, then deletes the S3 object."""
        key = self._s3_key_for_path(path_entry)
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}.zip".format(path_entry["folder_name"], date)

        print("======================> Downloading s3://{}/{} to {}".format(
            self.BUCKET_NAME, key, zip_name))

        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, key, zip_name)

        try:
            import zipfile
            target = os.path.join(self.workspace_path, self.workspace_name)
            with zipfile.ZipFile(zip_name, 'r') as zf:
                zf.extractall(target)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        print("======================> Deleting s3://{}/{}".format(self.BUCKET_NAME, key))
        s3.delete_object(Bucket=self.BUCKET_NAME, Key=key)

        return "success"

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow)
    # ------------------------------------------------------------------ #

    def archive_data(self):
        self.generate_full_compressed_data()
        print("======================> Uploading archive {} to bucket {}".format(
            self.archive_zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.upload_file(self.archive_zip_name, self.BUCKET_NAME, self.archive_s3_key)
        self.perform_archive_cleanup()

    def backup_data(self):
        self.generate_compressed_data()
        print("======================> Uploading file {} to bucket {}".format(
            self.zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.upload_file(self.zip_name, self.BUCKET_NAME, self.s3_key)
        self.perform_cleanup()

    def restore_data(self):
        print("======================> Downloading file {} from bucket {}".format(
            self.zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, self.s3_key, self.zip_name)
        self.extract_from_compressed_data()
        self.perform_cleanup()

    def restore_archive_data(self):
        print("======================> Downloading archive {} from bucket {}".format(
            self.archive_zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, self.archive_s3_key, self.archive_zip_name)
        self.extract_from_archive_data()
        self.perform_archive_cleanup()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_aws_source.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add wbck/sources/aws.py tests/test_aws_source.py
git commit -m "feat: update AwsSource to read source_credentials, add backup_path/restore_path"
```

---

## Task 6: Update local.py — new init + backup_path/restore_path

**Files:**
- Modify: `wbck/sources/local.py`
- Create: `tests/test_local_source.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_local_source.py`:

```python
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


def test_restore_path_extracts_and_deletes_source(new_config, tmp_path):
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

    os.chdir(str(tmp_path))
    status = source.restore_path(path_entry)

    assert status == "success"
    assert not zip_path.exists()
    restored = tmp_path / "test-workspace" / "notes" / "hello.txt"
    assert restored.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_local_source.py -v 2>&1 | head -20
```

Expected: failures (LocalSource reads `source_settings.local.local_path` which no longer exists).

- [ ] **Step 3: Rewrite local.py**

```python
import os
import shutil
import zipfile
from datetime import datetime

from .base import BaseSource


class LocalSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        local_creds = self.source_credentials.get("local", {})
        self.local_path = local_creds.get("root_path", "")

    def _dest_path_for_entry(self, path_entry):
        """Returns the full destination file path for a path entry."""
        if path_entry.get("backup_location"):
            return path_entry["backup_location"]
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}.zip".format(path_entry["folder_name"], date)
        return os.path.join(self.local_path, self.workspace_name, zip_name)

    # ------------------------------------------------------------------ #
    # Path-level methods
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """Zips the path and copies to local destination. Returns ('success'|'failed', note)."""
        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"Local backup root '{self.local_path}' does not exist")

        zip_name = self._make_path_zip(path_entry, paths_to_exclude)
        dest = self._dest_path_for_entry(path_entry)

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print("======================> Copying {} to {}".format(zip_name, dest))

        try:
            shutil.copy(zip_name, dest)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        return "success", ""

    def restore_path(self, path_entry):
        """Copies zip from local source, extracts it, then deletes the source zip."""
        source_zip = self._dest_path_for_entry(path_entry)

        date = datetime.now().date().isoformat()
        local_zip = "{}-{}.zip".format(path_entry["folder_name"], date)

        print("======================> Copying {} to {}".format(source_zip, local_zip))
        shutil.copy(source_zip, local_zip)

        try:
            target = os.path.join(self.workspace_path, self.workspace_name)
            with zipfile.ZipFile(local_zip, 'r') as zf:
                zf.extractall(target)
        finally:
            if os.path.exists(local_zip):
                os.remove(local_zip)

        print("======================> Deleting source zip {}".format(source_zip))
        os.remove(source_zip)

        return "success"

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow)
    # ------------------------------------------------------------------ #

    def archive_data(self):
        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"{self.local_path} does not exist")
        self.generate_full_compressed_data()
        print("======================> Uploading archive {} to folder {}".format(
            self.archive_zip_name, self.local_path))
        shutil.copy(self.archive_zip_name, self.local_path)
        self.perform_archive_cleanup()

    def restore_archive_data(self):
        print("======================> Downloading archive {} from folder {}".format(
            self.archive_zip_name, self.local_path))
        archive_path = os.path.join(self.local_path, self.archive_zip_name)
        shutil.copy(archive_path, self.archive_zip_name)
        self.extract_from_archive_data()
        self.perform_archive_cleanup()

    def backup_data(self):
        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"{self.local_path} does not exist")
        self.generate_compressed_data()
        print("======================> Uploading file {} to folder {}".format(
            self.zip_name, self.local_path))
        shutil.copy(self.zip_name, self.local_path)
        self.perform_cleanup()

    def restore_data(self):
        print("======================> Downloading file {} from folder {}".format(
            self.zip_name, self.local_path))
        backup_path = os.path.join(self.local_path, self.zip_name)
        shutil.copy(backup_path, self.zip_name)
        self.extract_from_compressed_data()
        self.perform_cleanup()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_local_source.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add wbck/sources/local.py tests/test_local_source.py
git commit -m "feat: update LocalSource to read source_credentials, add backup_path/restore_path"
```

---

## Task 7: Export GitSource from sources/__init__.py

**Files:**
- Modify: `wbck/sources/__init__.py`

- [ ] **Step 1: Read current __init__.py**

```bash
cat wbck/sources/__init__.py
```

- [ ] **Step 2: Replace wbck/sources/__init__.py with**

```python
from .base import BaseSource
from .aws import AwsSource
from .local import LocalSource
from .git import GitSource


__all__ = [
    "BaseSource",
    "LocalSource",
    "AwsSource",
    "GitSource"
]
```

- [ ] **Step 3: Verify**

```bash
python3 -c "from wbck.sources import AwsSource, LocalSource, GitSource; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add wbck/sources/__init__.py
git commit -m "feat: export GitSource from sources package"
```

---

## Task 8: Rewrite runners.py — path-centric loop

**Files:**
- Modify: `wbck/runners.py`
- Create: `tests/test_runners.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_runners.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, call
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
         patch("wbck.runners.LocalSource", return_value=mock_handler):
        restore_data(str(p), force=True)

    assert mock_handler.restore_archive_data.called
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_runners.py -v 2>&1 | head -30
```

Expected: failures — runner still uses old source_settings-based logic.

- [ ] **Step 3: Rewrite runners.py**

```python
import os
import json
import shutil
from .sources import AwsSource, LocalSource, GitSource
from .utils import open_log, write_log, print_summary


_PKG_DIR = os.path.dirname(__file__)


def _get_handler(source, config_data):
    if source == "s3":
        return AwsSource(config_data)
    if source == "local":
        return LocalSource(config_data)
    if source == "git":
        return GitSource(config_data)
    raise ValueError(f"Unknown backup source: '{source}'")


def setup_from_template(workspace_name, workspace_path, config_folder):
    """Creates the workspace in a specific path based on the template."""
    src_path = os.path.join(_PKG_DIR, "structure")
    dst_path = os.path.join(workspace_path, workspace_name)

    if os.path.exists(dst_path):
        print("Skipping creation as workspace {} in path {} already exists".format(
            workspace_name, workspace_path))
        return

    print("Creating workspace {}".format(workspace_name))
    shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns('.keep'))

    with open(os.path.join(_PKG_DIR, "config_template.json")) as f:
        data = json.load(f)

    data["name"] = workspace_name
    data["workspace_path"] = workspace_path

    config_path = "{}/{}_config.json".format(config_folder, workspace_name)
    with open(config_path, "w") as f:
        json.dump(data, f)


def backup_data(config_path):
    """
    Path-centric backup. If workspace enabled=0, performs full archival.
    Otherwise iterates paths_to_include and dispatches to per-source handlers.
    Logs all results and prints a summary at the end.
    """
    with open(config_path, 'r') as f:
        config_data = json.load(f)

    workspace_name = config_data["name"]
    is_enabled = bool(config_data["enabled"])

    if not is_enabled:
        enabled_sources = [
            src
            for src in config_data.get("source_credentials", {})
            if src != "git"
        ]
        for src in enabled_sources:
            handler = _get_handler(src, config_data)
            print("Workspace is disabled — archiving full workspace using {}".format(src))
            handler.archive_data()
        return

    log_fh, log_path = open_log(workspace_name)
    results = []
    paths_to_exclude = config_data.get("paths_to_exclude", [])

    try:
        for path_entry in config_data.get("paths_to_include", []):
            if not bool(path_entry.get("enabled", 1)):
                write_log(log_fh, path_entry["folder_name"], "—", "SKIPPED", "disabled in config")
                results.append((path_entry["folder_name"], "—", "skipped", "disabled in config"))
                continue

            for source in path_entry.get("backup_source", []):
                handler = _get_handler(source, config_data)
                try:
                    status, note = handler.backup_path(path_entry, paths_to_exclude)
                except Exception as e:
                    status, note = "failed", str(e)
                write_log(log_fh, path_entry["folder_name"], source, status.upper(), note)
                results.append((path_entry["folder_name"], source, status, note))
    finally:
        log_fh.close()

    print_summary(results, workspace_name, log_path)


def restore_data(config_path, force=False):
    """
    Path-centric restore. Skips disabled workspaces unless --force.
    --force restores from the full workspace archive.
    Otherwise iterates paths_to_include and dispatches to per-source handlers.
    """
    with open(config_path, 'r') as f:
        config_data = json.load(f)

    is_enabled = bool(config_data["enabled"])

    if not is_enabled and not force:
        print("Skipping workspace '{}' — it is disabled and marked for archival. "
              "Set enabled=1 in the config to restore it, or use --force to restore from archive.".format(
                  config_data["name"]))
        return

    if not is_enabled and force:
        enabled_sources = [
            src
            for src in config_data.get("source_credentials", {})
            if src != "git"
        ]
        for src in enabled_sources:
            handler = _get_handler(src, config_data)
            print("Force-restoring archive for workspace '{}' using {}".format(
                config_data["name"], src))
            handler.restore_archive_data()
        return

    for path_entry in config_data.get("paths_to_include", []):
        if not bool(path_entry.get("enabled", 1)):
            print("Skipping disabled path: {}".format(path_entry["folder_name"]))
            continue

        for source in path_entry.get("backup_source", []):
            handler = _get_handler(source, config_data)
            print("Restoring '{}' using {}".format(path_entry["folder_name"], source))
            handler.restore_path(path_entry)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_runners.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add wbck/runners.py tests/test_runners.py
git commit -m "feat: rewrite runners with path-centric loop, logging, and summary output"
```

---

## Task 9: Final verification and push

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass with no warnings.

- [ ] **Step 2: Verify CLI still loads**

```bash
python3 -c "from wbck import cli; print('cli ok')"
```

Expected: `cli ok`

- [ ] **Step 3: Verify syntax of all changed files**

```bash
python3 -c "
import ast
files = [
    'wbck/sources/base.py',
    'wbck/sources/aws.py',
    'wbck/sources/local.py',
    'wbck/sources/git.py',
    'wbck/utils.py',
    'wbck/runners.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'ok: {f}')
"
```

Expected: `ok: <each file>`

- [ ] **Step 4: Push**

```bash
git push origin master
```

# Config Redesign — Design Spec
**Date:** 2026-06-05

## Problem

The current config conflates two concerns: _what_ to back up (`repositories`, `folders_to_maintain`) and _how_ to back it up (`source_settings.enabled_sources`). This makes it impossible to route different paths to different sources and forces a rigid workspace structure. `repositories` and `folders_to_maintain` are separate lists that represent the same concept — a path inside a workspace that needs to be persisted somewhere.

## Goal

Unify all paths into a single `paths_to_include` list where each entry declares its own backup source(s). Move credentials into a dedicated `source_credentials` block. Replace file-level exclude buried in source settings with a workspace-level `paths_to_exclude` list.

---

## Section 1 — Config Structure

### New `config_template.json`

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
        },
        {
            "folder_name": "notes",
            "folder_path": "notes",
            "backup_source": ["s3", "local"],
            "backup_location": "",
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

### `paths_to_include` fields

| Field | Type | Required | Description |
|---|---|---|---|
| `folder_name` | string | yes | Human label for this path |
| `folder_path` | string | yes | Relative path within `workspace_path/workspace_name` |
| `backup_source` | list | yes | One or more of `"s3"`, `"local"`, `"git"` |
| `backup_location` | string | no (yes for git) | Override destination; for git this is the repo URL |
| `enabled` | int | yes | `1` = active, `0` = skip this path |

### Default backup path generation

For `s3` and `local`, if `backup_location` is empty the destination is auto-generated:

```
<root_path>/<workspace_name>/<folder_name>-<YYYY-MM-DD>.zip
```

`root_path` is the standardised key across all source credentials (bucket name for S3, directory for local). If `backup_location` is specified it takes full precedence.

For `git`, `backup_location` is the repo URL and is required.

### `source_credentials`

- **s3**: `root_path` (bucket name), `aws_key`, `aws_secret`, `aws_profile`. If `aws_profile` is set, key/secret are not required. S3 auth follows the existing profile-or-key/secret logic.
- **local**: `root_path` (directory path on disk).
- **git**: `auth_method` (`"ssh"` or `"https"`). No stored secrets — SSH relies on the system SSH agent; HTTPS relies on the OS git credential helper (e.g. macOS Keychain).

### `paths_to_exclude`

Workspace-level list of folder/file names to exclude when compressing any path (e.g. `.venv`, `node_modules`, `build`, `dist`). Applied to all S3 and local backup operations.

### Removed fields

- `repositories` — replaced by `paths_to_include` entries with `backup_source: ["git"]`
- `source_settings.enabled_sources` — routing is now per path
- `source_settings.folders_to_maintain` — replaced by `paths_to_include`
- `source_settings.files_to_exclude` — replaced by workspace-level `paths_to_exclude`

### Migration

No automated migration. Users rewrite configs manually. The `config_template.json` is updated to the new structure.

---

## Section 2 — Runner / Processing Flow

### Approach: path-centric loop (Option A)

Loop over `paths_to_include`. For each path, loop over its `backup_source` list. Each source handler receives one path entry and returns a status string.

### Backup

```
open log file: /tmp/wbck-<workspace_name>-<YYYYMMDD-HHMMSS>.log
results = []

if workspace enabled=0:
    run full archival (existing behaviour — unchanged)
    return

for each path in paths_to_include:
    if path.enabled=0:
        log SKIPPED — disabled
        continue
    for each source in path.backup_source:
        handler = get_handler(source, source_credentials)
        status, note = handler.backup_path(path, paths_to_exclude)
        write to log file
        results.append((path.folder_name, source, status, note))

print tabular summary (FAILED + SKIPPED rows only)
print log file path
```

### Restore

```
if workspace enabled=0 and not --force:
    print skip message
    return

if --force:
    restore from full archive (existing behaviour — unchanged)
    return

for each path in paths_to_include:
    if path.enabled=0: skip
    for each source in path.backup_source:
        handler.restore_path(path)
```

---

## Section 3 — Source Handler Interface

### New path-level methods on `BaseSource`

```python
def backup_path(self, path_entry: dict, paths_to_exclude: list) -> tuple[str, str]:
    """Returns (status, note). status: 'success' | 'skipped' | 'failed'"""
    raise NotImplementedError()

def restore_path(self, path_entry: dict) -> str:
    """Returns status string."""
    raise NotImplementedError()
```

Workspace-level `backup_data()` / `restore_data()` / `archive_data()` / `restore_archive_data()` are retained on `BaseSource` for the archival flow (`enabled=0`).

### File changes

| File | Change |
|---|---|
| `config_template.json` | Full rewrite to new structure |
| `sources/base.py` | Add `backup_path()`, `restore_path()` |
| `sources/aws.py` | Implement `backup_path()` (per-path zip + upload), `restore_path()` (download + extract + delete remote zip) |
| `sources/local.py` | Implement `backup_path()` (per-path zip + copy), `restore_path()` (copy + extract + delete local zip copy) |
| `sources/git.py` | New — interactive pause logic for backup, clone/pull for restore |
| `sources/__init__.py` | Export `GitSource` |
| `repositories.py` | Retained but `clone_repositories()` no longer called from runner |
| `runners.py` | Rewrite `backup_data()`, `restore_data()` to path-centric loop with logging |
| `utils.py` | Add `write_log()`, `print_summary()` |

---

## Section 4 — Git Source Handler

### `sources/git.py`

```python
class GitSource(BaseSource):

    def backup_path(self, path_entry, paths_to_exclude) -> tuple[str, str]:
        resolved = os.path.join(self.workspace_path, self.workspace_name, path_entry["folder_path"])

        while True:
            result = subprocess.run(
                ["git", "-C", resolved, "status", "--porcelain"],
                capture_output=True, text=True
            )
            if not result.stdout.strip():
                return "success", ""   # clean — remote already has latest

            print(f"\n[{path_entry['folder_name']}] has uncommitted changes.")
            print("  [R]etry  /  [C]ontinue  (auto-continue in 60s): ", end="", flush=True)
            choice = _prompt_with_timeout(60)   # "r", "c", or None on timeout

            if choice == "r":
                continue
            return "skipped", "uncommitted changes"

    def restore_path(self, path_entry) -> str:
        resolved = os.path.join(self.workspace_path, self.workspace_name, path_entry["folder_path"])
        repo_url = path_entry["backup_location"]

        if os.path.exists(resolved):
            subprocess.run(["git", "-C", resolved, "pull"], check=True)
        else:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            subprocess.run(["git", "clone", repo_url, resolved], check=True)

        return "success"
        # no post-restore delete for git
```

`_prompt_with_timeout(seconds)` uses `select.select` on `sys.stdin` to wait up to `seconds` for input, returns the lowercased first character or `None` on timeout.

---

## Section 5 — Logging and Summary

### Log file

Path: `/tmp/wbck-<workspace_name>-<YYYYMMDD-HHMMSS>.log`

Format per line:
```
[2026-06-05 14:32:01] [notes] [s3] SUCCESS
[2026-06-05 14:32:04] [configs] [local] FAILED — Permission denied
[2026-06-05 14:32:07] [workspace-backup] [git] SKIPPED — uncommitted changes
```

All statuses (success, failed, skipped) are written to the log. The log is opened at backup start and closed on completion.

### Terminal summary

Only `FAILED` and `SKIPPED` rows are printed — success rows are omitted to keep output scannable.

```
BACKUP SUMMARY — my-workspace
─────────────────────────────────────────────────────
 Folder              Source   Status    Note
─────────────────────────────────────────────────────
 configs             local    FAILED    Permission denied
 workspace-backup    git      SKIPPED   uncommitted changes
─────────────────────────────────────────────────────
 4 paths processed · 1 failed · 1 skipped

Full log: /tmp/wbck-my-workspace-20260605-143207.log
```

If all paths succeed, the summary prints a single success line with no table.

### S3 / Local failure behaviour

If `backup_path()` raises any exception, the runner catches it, logs `FAILED` with the error message, and auto-continues to the next path. No user prompt.

### Post-restore cleanup

After a successful `restore_path()` for S3 and local sources, the source zip is deleted:
- **S3**: `s3.delete_object(Bucket=bucket, Key=key)`
- **Local**: `os.remove(zip_path_on_disk)`

Git source: no deletion.

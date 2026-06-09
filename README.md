# Workspace Backup and Restoration Tool (wbck)

![Workspace Backup and Restoration Tool](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSJwvW-RmC7SNL2jCyhiW7vJHTEE_3XXj6RDH8QASwliQ&s)

## Introduction

Workspace Backup and Restoration Tool (wbck) is a utility designed to ease machine migrations and workspace setup without the fear of data loss. It backs up and restores your code folders, documents, and any other paths — each to the source that fits best (git remote, S3, or local disk).

Whether you're transitioning to a new machine or setting up a development environment elsewhere, wbck ensures your workspace is replicated exactly where it was, minimizing downtime and ensuring continuity in your workflow.

A *workspace* is all the data associated with a specific project or company context. You can define as many workspaces as you need and switch between them with a single command.

## Features

- **Per-path backup sources** — each folder in your workspace can back up to git, S3, or local storage independently.
- **Git-aware backup** — pushes unpushed commits to the remote, and falls back to a zip archive for repos with no push access or untracked changes.
- **Exact restoration** — each folder is restored to its configured path relative to the workspace root, preserving your directory structure.
- **Resume-safe restore** — already-restored paths are skipped on re-runs, so a failed restore can be continued from where it left off.
- **Workspace archival** — disabled workspaces are compressed into a single full archive for long-term storage.
- **Dry-run mode** — validate all paths and surface per-file issues without performing any backup.
- **Workspace contexts** — switch between multiple workspace configurations without specifying a config path on every command, similar to `kubectl config use-context`.
- **Targeted operations** — back up or restore a single folder by name without touching the rest of the workspace.

## Installation

```bash
pip install wbck
```

```bash
wbck --help
usage: wbck [-h] [--version] {create,backup,restore,cache} ...

Application to backup and restore my workspace data using config files

Commands:
  create    creates a new workspace
  backup    backup your workspace
  restore   restore your workspace
  cache     manage workspace contexts
```

## Configuration

Create a config file (`<workspace>_config.json`) in a configs directory. Here is a complete example:

```json
{
  "name": "my",
  "enabled": 1,
  "workspace_path": "/Users/arpit",
  "default_source": "s3",
  "paths_to_include": [
    {
      "folder_name": "portfolio-website",
      "folder_path": "codes/portfolio-website",
      "backup_source": ["git"],
      "backup_location": "git@github.com:argoyal/portfolio-website.git",
      "enabled": 1
    },
    {
      "folder_name": "documents",
      "folder_path": "documents",
      "backup_source": ["s3"],
      "enabled": 1
    },
    {
      "folder_name": "notes",
      "folder_path": "documents/notes",
      "backup_source": ["local"],
      "enabled": 1
    }
  ],
  "paths_to_exclude": [".venv", "node_modules", "build", "dist"],
  "source_credentials": {
    "s3": {
      "root_path": "my-backup-bucket",
      "aws_key": "",
      "aws_secret": "",
      "aws_profile": "myaws"
    },
    "local": {
      "root_path": "/Volumes/ExternalDrive/backups"
    },
    "git": {
      "auth_method": "ssh"
    }
  }
}
```

### Config reference

| Field | Description |
|---|---|
| `name` | Workspace identifier (e.g. `my`, `work`, `acme`) |
| `enabled` | `1` = active workspace, `0` = archived (backup creates a single full-workspace zip) |
| `workspace_path` | Absolute path to the directory that contains the workspace folder |
| `default_source` | Fallback source (`s3` or `local`) used when a git push fails or for workspace archival |
| `paths_to_exclude` | Folder/file names to skip when zipping (applied globally) |

### `paths_to_include` entries

| Field | Description |
|---|---|
| `folder_name` | Display name and prefix used for backup file naming |
| `folder_path` | Path to the folder **relative to** `<workspace_path>/<name>` |
| `backup_source` | List of sources: `"git"`, `"s3"`, `"local"` |
| `backup_location` | Git remote URL (required when `backup_source` includes `"git"`) |
| `enabled` | `0` skips this path during backup and restore |

### `source_credentials`

**S3:**

| Field | Description |
|---|---|
| `root_path` | S3 bucket name |
| `aws_profile` | AWS CLI profile name (preferred over key/secret) |
| `aws_key` / `aws_secret` | AWS credentials (used if no profile is set) |

**Local:**

| Field | Description |
|---|---|
| `root_path` | Absolute path to the local backup directory |

**Git:**

| Field | Description |
|---|---|
| `auth_method` | `"ssh"` or `"https"` |

## Usage

### 1. Workspace Contexts

Point wbck at a folder containing all your config files once, then switch between workspaces by name — no need to pass `--config-path` on every command.

```bash
# Set the config folder
wbck cache set --config-folder $HOME/.configs/
# Config folder set to: /home/user/.configs/
# Available configs: my, work
# Switch with: wbck cache use <name>

# List available workspaces (* = active)
wbck cache show
# Config folder: /home/user/.configs/
#
#   * my
#     work

# Switch active workspace
wbck cache use work

# Clear the context cache
wbck cache clear
```

You can always override the active context for a single command:

```bash
wbck backup --config-path /path/to/specific_config.json
```

### 2. Backup

```bash
# Backup the active workspace
wbck backup

# Backup a specific workspace by name
wbck backup my

# Backup all workspaces in the config folder
wbck backup --all

# Backup a single folder only
wbck backup --folder-name documents

# Validate paths without performing the backup
wbck backup --dry-run
```

**How git backup works:** wbck pushes any unpushed commits to the configured remote. If the repo has uncommitted changes or the remote is not writable, it commits everything to a local `local-dump` branch and falls back to a zip upload via `default_source`.

**Dry-run** zips every file in each path to surface encoding or permission issues without uploading anything.

### 3. Restore

```bash
# Restore the active workspace
wbck restore

# Restore a specific workspace by name
wbck restore my

# Restore all workspaces in the config folder
wbck restore --all

# Restore a single folder only
wbck restore --folder-name documents

# Keep the backup on the remote after restoring
wbck restore --keep-remote-data

# Force restore a disabled (archived) workspace
wbck restore --force
```

**Resume safety:** if a restore run is interrupted, already-restored paths are automatically skipped on the next run, so you can re-run `wbck restore` to pick up from the failure point.

**`--force`** restores from the full-workspace archive created when `enabled` is set to `0` in the config.

### 4. Create a New Workspace

```bash
wbck create --name myworkspace --workspace-path $HOME/ --config-folder $HOME/.configs/
```

This creates the workspace directory at `<workspace-path>/<name>` and writes a starter config file to `<config-folder>/<name>_config.json`.

## Contributing

Contributions are welcome! Feel free to submit bug reports, feature requests, or pull requests on [GitHub](https://github.com/argoyal/wbck).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Disclaimer:** This project is provided as-is, without warranty of any kind, express or implied. Use at your own risk.

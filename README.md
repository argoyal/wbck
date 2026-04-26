# Workspace Backup and Restoration Tool (wbck)

![Workspace Backup and Restoration Tool](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSJwvW-RmC7SNL2jCyhiW7vJHTEE_3XXj6RDH8QASwliQ&s)

## Introduction

Workspace Backup and Restoration Tool (wbck) is a simple utility designed to ease the process of changing machines without the fear of data loss during migration. It provides a seamless solution for backing up and restoring workspace configurations and repositories.

Whether you're transitioning to a new computer or setting up a development environment on another machine, wbck ensures that your workspace is replicated effortlessly, minimizing downtime and ensuring continuity in your workflow.

I classify workspace as all the data associated to a specific project/company I have been part of. People might have different opinions of defining them and can structure it accordingly using the configuration files.

## Features

- **Configuration Driven**: Utilize a configuration file to specify the repositories you want to backup and restore, allowing for easy customization.
- **Exact Cloning**: Restore your repositories exactly where they were before, ensuring consistency across machines.
- **Workspace Contexts**: Switch between multiple workspace configurations without specifying a config file path on every command — similar to `kubectl config use-context`.
- **Simple Installation**: Install wbck from the PyPI repository using pip, making it accessible and easy to set up.

## Installation

```bash
pip install wbck
```

```bash
wbck --help
usage: wbck [-h] {create,backup,restore,cache} ...

Application to backup and restore my workspace data using config files

Commands:
  create              creates a new workspace
  backup              backup your workspace
  restore             restore your workspace
  cache               manage workspace contexts
```

## Usage

### 1. Configuration Setup

Create a configuration file (`<workspace>_config.json`) in a configs directory. Here's an example configuration:

```json
{
  "name": "",
  "enabled": 1,
  "workspace_path": "",
  "repositories": [{
    "clone_name": "workspace-backup",
    "clone_path": "codes/internal",
    "repo_url": "https://github.com/argoyal/workspace-backup.git"
  }],
  "source_settings": {
    "enabled_sources": ["s3", "local"],
    "folders_to_maintain": [],
    "files_to_exclude": [],
    "s3": {
      "bucket_name": "",
      "aws_key": "",
      "aws_secret": ""
    },
    "local": {
      "local_path": ""
    }
  }
}
```

| Parameter | Description | Value/s |
|----------|----------|----------|
| name   | Name of workspace you are dealing with   | str (eg. microsoft, google etc.)  |
| enabled   | Disables execution of any command on this config file   | int (1 for enabled, 0 for disabled)   |
| workspace_path   | Path where the workspace folder's root exist   | str (eg. $HOME/microsoft), $HOME needs to be expanded  |
| repositories[].clone_name   | Name of the repository after cloned locally   | str   |
| repositories[].clone_path   | Path where the repository should be cloned. The paths are relative to the workspace path root   | str (eg. codes/internal)  |
| repositories[].repo_url   | Repository URL from where the cloning is to be done   | str (eg. https://github.com/argoyal/wbck)  |
| source_settings.enabled_sources   | Sources for data backup. If you specify multiple, data will be stored in all of them   | list (s3, local)  |
| source_settings.folders_to_maintain   | Folders that need to be compressed as zip for backup. Paths are relative to the workspace root folder   | list (eg. [documents/, 'data/'])  |
| source_settings.files_to_exclude   | Files/folders that need to be excluded while backing up   | list  |
| source_settings.s3.bucket_name   | Name of the bucket where backup is to be pushed   | str  |
| source_settings.s3.aws_key   | AWS Key   | str  |
| source_settings.s3.aws_secret   | AWS Secret   | str  |
| source_settings.local.local_path   | Local path where the data backup needs to happen   | str  |

### 2. Workspace Contexts

wbck supports switching between multiple workspace configurations without specifying `--config-path` on every command. Point wbck at a folder containing all your config files once, then switch between them by name.

#### Set the config folder

```bash
wbck cache set --config-folder $HOME/.configs/
# Config folder set to: /home/user/.configs/
# Available configs: asterhq, microsoft
# Switch with: wbck cache use <name>
```

#### List available workspaces

```bash
wbck cache show
# Config folder: /home/user/.configs/
#
#   * asterhq
#     microsoft
```

The `*` marks the currently active workspace.

#### Switch the active workspace

```bash
wbck cache use microsoft
# Switched to: microsoft

wbck cache show
# Config folder: /home/user/.configs/
#
#     asterhq
#   * microsoft
```

#### Clear the context cache

```bash
wbck cache clear
```

#### Override per command

You can always pass `--config-path` explicitly to bypass the active context for a single run:

```bash
wbck backup --config-path /path/to/specific_config.json
```

### 3. Backup Workspace

```bash
# Using the active context
wbck backup

# Or with an explicit config path
wbck backup --config-path $HOME/.configs/asterhq_config.json
```

### 4. Restore Workspace

```bash
# Using the active context
wbck restore

# Or with an explicit config path
wbck restore --config-path $HOME/.configs/asterhq_config.json
```

### 5. Create Workspace

Create a new workspace from the default folder template:

```bash
wbck create --name workspace --workspace-path $HOME/ --config-folder $HOME/.configs/
```

```bash
wbck create --help
usage: wbck create [-h] --name NAME [--workspace-path WORKSPACE_PATH] --config-folder CONFIG_FOLDER

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           name of the new workspace
  --workspace-path WORKSPACE_PATH
                        path where the workspace needs to be created
  --config-folder CONFIG_FOLDER
                        path where the config for this workspace is
```

This creates the workspace directory at `<workspace-path>/<name>` and writes a starter config file to `<config-folder>/<name>_config.json`.

## Contributing

Contributions are welcome! Feel free to submit bug reports, feature requests, or pull requests on [GitHub](https://github.com/argoyal/wbck).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Disclaimer:** This project is provided as-is, without warranty of any kind, express or implied. Use at your own risk.

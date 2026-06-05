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

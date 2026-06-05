import os
import json
import shutil
from .sources import AwsSource, LocalSource, GitSource
from .utils import open_log, write_log, print_summary, print_dry_run_summary, print_unreachable_remotes, print_unpushable_remotes


_PKG_DIR = os.path.dirname(__file__)


def _resolve_archive_source(config_data):
    """Resolves which non-git source to use for workspace archival.
    Uses default_source if set, else auto-selects if only one, else prompts."""
    default = config_data.get("default_source", "")
    enabled_sources = [
        src for src in config_data.get("source_credentials", {})
        if src != "git"
    ]
    if not enabled_sources:
        raise SystemExit("No archive sources configured in source_credentials.")
    if default and default in enabled_sources:
        return default
    if len(enabled_sources) == 1:
        return enabled_sources[0]
    print("Choose an archive source:")
    for i, src in enumerate(enabled_sources, 1):
        print("  {}) {}".format(i, src))
    raw = input("Select [1-{}]: ".format(len(enabled_sources))).strip()
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(enabled_sources):
            raise ValueError()
        return enabled_sources[idx]
    except ValueError:
        raise SystemExit("Invalid selection.")


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


def backup_data(config_path, dry_run=False, folder_name=None):
    """
    Path-centric backup. If workspace enabled=0, performs full archival.
    Otherwise iterates paths_to_include and dispatches to per-source handlers.
    Logs all results and prints a summary at the end.

    When dry_run=True, validates each path without performing the actual backup:
    - Git sources: reports staged and unstaged changes
    - S3/local sources: runs the zip cycle to catch per-file issues
    """
    with open(config_path, 'r') as f:
        config_data = json.load(f)

    workspace_name = config_data["name"]
    is_enabled = bool(config_data["enabled"])

    if not is_enabled and not dry_run:
        choice = _resolve_archive_source(config_data)
        handler = _get_handler(choice, config_data)
        print("Archiving full workspace using {}".format(choice))
        handler.archive_data()
        return

    if not is_enabled and dry_run:
        print("DRY RUN — workspace '{}' is disabled, checking full workspace zip".format(
            workspace_name))
        from .sources.base import BaseSource
        handler = BaseSource(config_data)
        print("  checking full workspace archive ...")
        try:
            issues = handler.dry_run_full_workspace()
        except Exception as e:
            issues = [(".", str(e))]
        dry_results = [(workspace_name, "archive", issues, "")]
        print_dry_run_summary(dry_results, workspace_name)
        return

    paths_to_exclude = config_data.get("paths_to_exclude", [])
    paths_to_include = config_data.get("paths_to_include", [])
    if folder_name:
        paths_to_include = [p for p in paths_to_include if p["folder_name"] == folder_name]
        if not paths_to_include:
            raise SystemExit("error: folder '{}' not found in paths_to_include".format(folder_name))

    if dry_run:
        print("DRY RUN — checking paths for '{}'".format(workspace_name))
        dry_results = []
        unreachable = []
        unpushable = []

        for path_entry in paths_to_include:
            folder_path = path_entry.get("folder_path", "")
            if not bool(path_entry.get("enabled", 1)):
                dry_results.append((path_entry["folder_name"], "—", [(".", "disabled in config")], folder_path))
                continue

            for source in path_entry.get("backup_source", []):
                handler = _get_handler(source, config_data)
                print("  checking {} [{}] ...".format(path_entry["folder_name"], source))
                try:
                    issues = handler.dry_run_path(path_entry, paths_to_exclude)
                except Exception as e:
                    issues = [(".", str(e))]
                dry_results.append((path_entry["folder_name"], source, issues, folder_path))

                if source == "git":
                    fallback = handler._resolve_fallback_source()
                    try:
                        remote_url, reach_err, push_err = handler.check_remote(path_entry)
                        if reach_err:
                            unreachable.append((path_entry["folder_name"], remote_url, reach_err, folder_path))
                        elif push_err:
                            unpushable.append((
                                path_entry["folder_name"], remote_url,
                                fallback or "none", folder_path
                            ))
                    except Exception as e:
                        unreachable.append((
                            path_entry["folder_name"],
                            path_entry.get("backup_location", "unknown"),
                            str(e),
                            folder_path
                        ))

        print_dry_run_summary(dry_results, workspace_name)
        if unreachable:
            print_unreachable_remotes(unreachable)
        if unpushable:
            print_unpushable_remotes(unpushable)
        return

    log_fh, log_path = open_log(workspace_name)
    results = []

    try:
        for path_entry in paths_to_include:
            if not bool(path_entry.get("enabled", 1)):
                write_log(log_fh, path_entry["folder_name"], "—", "SKIPPED", "disabled in config")
                results.append((path_entry["folder_name"], "—", "skipped", "disabled in config"))
                continue

            for source in path_entry.get("backup_source", []):
                handler = _get_handler(source, config_data)
                try:
                    if source == "git":
                        status, note = handler.backup_path(
                            path_entry, paths_to_exclude, config_path=config_path)
                    else:
                        status, note = handler.backup_path(path_entry, paths_to_exclude)
                except Exception as e:
                    status, note = "failed", str(e)
                write_log(log_fh, path_entry["folder_name"], source, status.upper(), note)
                results.append((path_entry["folder_name"], source, status, note))
    finally:
        log_fh.close()

    print_summary(results, workspace_name, log_path)


def restore_data(config_path, force=False, keep_remote=False, folder_name=None):
    """
    Path-centric restore. Skips disabled workspaces unless --force.
    --force restores from the full workspace archive.
    --keep-remote-data prevents deletion of the backup from the remote source.
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
        choice = _resolve_archive_source(config_data)
        handler = _get_handler(choice, config_data)
        print("Force-restoring archive for workspace '{}' using {}".format(
            config_data["name"], choice))
        handler.restore_archive_data(keep_remote=keep_remote)
        return

    paths_to_include = config_data.get("paths_to_include", [])
    if folder_name:
        paths_to_include = [p for p in paths_to_include if p["folder_name"] == folder_name]
        if not paths_to_include:
            raise SystemExit("error: folder '{}' not found in paths_to_include".format(folder_name))

    for path_entry in paths_to_include:
        if not bool(path_entry.get("enabled", 1)):
            print("Skipping disabled path: {}".format(path_entry["folder_name"]))
            continue

        for source in path_entry.get("backup_source", []):
            handler = _get_handler(source, config_data)
            print("Restoring '{}' using {}".format(path_entry["folder_name"], source))
            handler.restore_path(path_entry, keep_remote=keep_remote)

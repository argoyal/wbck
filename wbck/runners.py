import os
import json
import shutil
from .sources import AwsSource, LocalSource
from .repositories import clone_repositories


_PKG_DIR = os.path.dirname(__file__)


def setup_from_template(workspace_name, workspace_path, config_folder):
    """
    creates the workspace in specific path based on the template
    """

    src_path = os.path.join(_PKG_DIR, "structure")
    dst_path = os.path.join(workspace_path, workspace_name)

    if os.path.exists(dst_path):
        print("Skipping creation as workspace {} in path {} already exists".format(
            workspace_name, workspace_path)
        )
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
    calls the appropriate backup data class depending
    on enabled sources. If the workspace is disabled, performs a full
    archival backup instead of a normal incremental backup.
    """

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    class_mapping = {
        "s3": AwsSource(config_data),
        "local": LocalSource(config_data)
    }

    enabled_sources = config_data["source_settings"]["enabled_sources"]
    is_enabled = bool(config_data["enabled"])

    for src in enabled_sources:
        if is_enabled:
            print("Backing up data using {}".format(src))
            class_mapping[src].backup_data()
        else:
            print("Workspace is disabled — archiving full workspace using {}".format(src))
            class_mapping[src].archive_data()


def restore_data(config_path, force=False):
    """
    calls the appropriate restore data class depending
    on enabled sources. Skips restoration if the workspace is disabled,
    unless force=True in which case the full archive is restored instead.
    """

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    is_enabled = bool(config_data["enabled"])

    if not is_enabled and not force:
        print("Skipping workspace '{}' — it is disabled and marked for archival. "
              "Set enabled=1 in the config to restore it, or use --force to restore from archive.".format(
                  config_data["name"]))
        return

    class_mapping = {
        "s3": AwsSource(config_data),
        "local": LocalSource(config_data)
    }

    enabled_sources = config_data["source_settings"]["enabled_sources"]

    clone_repositories(config_data)

    for src in enabled_sources:
        if not is_enabled and force:
            print("Force-restoring archive for workspace '{}' using {}".format(
                config_data["name"], src))
            class_mapping[src].restore_archive_data()
        else:
            print("Restoring data using {}".format(src))
            class_mapping[src].restore_data()

import os
import json
import shutil
from .sources.aws import AwsSource
from .sources.local import LocalSource
from .repositories import clone_repositories


def setup_from_template(workspace_name, workspace_path, config_folder):
    """
    creates the workspace in specific path based on the template
    """

    src_path = "structure"
    dst_path = os.path.join(workspace_path, workspace_name)

    if os.path.exists(dst_path):
        print("Skipping creation as workspace {} in path {} already exists".format(
            workspace_name, workspace_path)
        )
        return

    print("Creating workspace {}".format(workspace_name))
    shutil.copytree(src_path, dst_path)

    with open("config_template.json") as f:
        data = json.load(f)
    
    data["name"] = workspace_name
    data["workspace_path"] = workspace_path

    config_path = "{}/{}_config.json".format(config_folder, workspace_name)

    with open(config_path, "w") as f:
        json.dump(data, f)


def backup_data(config_path):
    """
    calls the appropriate backup data class depending
    on enabled sources
    """

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    class_mapping = {
        "s3": AwsSource(config_data),
        "local": LocalSource(config_data)
    }

    enabled_sources = config_data["source_settings"]["enabled_sources"]

    for src in enabled_sources:
        print("Backing up data using {}".format(src))
        class_mapping[src].backup_data()


def restore_data(config_path):
    """
    calls the appropriate restore data class depending
    on enabled sources
    """

    with open(config_path, 'r') as f:
        config_data = json.load(f)

    class_mapping = {
        "s3": AwsSource(config_data),
        "local": LocalSource(config_data)
    }

    enabled_sources = config_data["source_settings"]["enabled_sources"]

    clone_repositories(config_data)

    for src in enabled_sources:
        print("Backing up data using {}".format(src))
        class_mapping[src].restore_data()
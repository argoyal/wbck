import os
import argparse
from .runners import backup_data, restore_data, setup_from_template
from .load_config import is_config_loadable


def restore_workspace(args):
    is_config_loadable(args.config_path)
    restore_data(args.config_path)


def backup_workspace(args):
    is_config_loadable(args.config_path)
    backup_data(args.config_path)


def create_new_workspace(args):
    setup_from_template(args.name, args.workspace_path, args.config_folder)


def cli():
    """
    defines the entire cli parsing components of wbck
    """

    parser = argparse.ArgumentParser(
        description='Application to backup and restore my workspace data using config files'
    )
    subparsers = parser.add_subparsers(title="Commands")

    create_parser = subparsers.add_parser(
        "create",
        help="creates a new workspace"
    )
    create_parser.add_argument(
        "--name",
        required=True,
        help="name of the new workspace"
    )
    create_parser.add_argument(
        "--workspace-path",
        default=os.path.expanduser("~"),
        help="path where the workspace needs to be created"
    )
    create_parser.add_argument(
        "--config-folder",
        required=True,
        help="path where the config for this workspace is"
    )
    create_parser.set_defaults(func=create_new_workspace)

    backup_parser = subparsers.add_parser(
        "backup",
        help="commands pertaining to backup of your workspaces"
    )
    backup_parser.add_argument(
        "--config-path",
        required=True,
        help="path where the config for this workspace is"
    )
    backup_parser.set_defaults(func=backup_workspace)

    restore_parser = subparsers.add_parser(
        "restore",
        help="commands pertaining to restore of your workspaces"
    )
    restore_parser.add_argument(
        "--config-path",
        required=True,
        help="path where the config for this workspace is"
    )
    restore_parser.set_defaults(func=restore_workspace)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()

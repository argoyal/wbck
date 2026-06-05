import os
import argparse
from .runners import backup_data, restore_data, setup_from_template
from .cache import get_active_config_path, set_config_folder, use_config, show_configs, clear_cache


def _resolve_config_path(args):
    path = getattr(args, "config_path", None)
    if not path:
        path = get_active_config_path()
    if not path:
        raise SystemExit(
            "error: no active config. Set a folder with: wbck cache set --config-folder <path>\n"
            "       then switch to a config with:        wbck cache use <name>"
        )
    return path


def restore_workspace(args):
    config_path = _resolve_config_path(args)
    restore_data(config_path)


def backup_workspace(args):
    config_path = _resolve_config_path(args)
    backup_data(config_path)


def create_new_workspace(args):
    setup_from_template(args.name, args.workspace_path, args.config_folder)


def manage_cache(args):
    cmd = args.cache_command
    if cmd == "set":
        set_config_folder(args.config_folder)
    elif cmd == "use":
        use_config(args.name)
    elif cmd == "show":
        show_configs()
    elif cmd == "clear":
        clear_cache()
    else:
        args.cache_parser.print_help()


def cli():
    parser = argparse.ArgumentParser(
        description='Application to backup and restore my workspace data using config files'
    )
    subparsers = parser.add_subparsers(title="Commands")

    # create
    create_parser = subparsers.add_parser("create", help="creates a new workspace")
    create_parser.add_argument("--name", required=True, help="name of the new workspace")
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

    # backup
    backup_parser = subparsers.add_parser("backup", help="backup your workspace")
    backup_parser.add_argument(
        "--config-path",
        default=None,
        help="explicit config file path (overrides active context)"
    )
    backup_parser.set_defaults(func=backup_workspace)

    # restore
    restore_parser = subparsers.add_parser("restore", help="restore your workspace")
    restore_parser.add_argument(
        "--config-path",
        default=None,
        help="explicit config file path (overrides active context)"
    )
    restore_parser.set_defaults(func=restore_workspace)

    # cache
    cache_parser = subparsers.add_parser("cache", help="manage workspace contexts")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command")

    cache_set = cache_subparsers.add_parser("set", help="set the folder containing config files")
    cache_set.add_argument("--config-folder", required=True, help="path to the folder with config files")

    cache_use = cache_subparsers.add_parser("use", help="switch the active config (workspace context)")
    cache_use.add_argument("name", help="workspace name to activate")

    cache_subparsers.add_parser("show", help="list all configs with active one marked")
    cache_subparsers.add_parser("clear", help="clear all cached context settings")

    cache_parser.set_defaults(func=manage_cache, cache_parser=cache_parser)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    cli()

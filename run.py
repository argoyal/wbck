import argparse
from app.load_config import load_config
from app.repositories import clone_repositories
from app.aws import download_data, upload_data
from app.templates import create_template


def setup_applications():
    config_data = load_config()
    list(map(clone_repositories, config_data))
    list(map(download_data, config_data))


def sync_applications():
    config_data = load_config()

    list(map(upload_data, config_data))


def create_new_workspace():
    config_data = load_config()

    list(map(create_template, config_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Application to sync my workspace data using config files'
    )

    parser.add_argument(
        "--setup",
        help="setup all the active workspaces",
        action="store_true"
    )
    parser.add_argument(
        "--sync",
        help="sync all the active workspaces",
        action="store_true"
    )
    parser.add_argument(
        "--add",
        help="creates a specific path of workspace using structure",
        action="store_true"
    )

    args = vars(parser.parse_args())

    if args["setup"]:
        setup_applications()
    if args["sync"]:
        sync_applications()
    if args["add"]:
        create_new_workspace()

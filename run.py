import argparse
from app.load_config import load_config
from app.repositories import clone_repositories
from app.aws import download_data, upload_data
from app.templates import create_template


def setup_applications(app=None):
    config_data = load_config()

    if app:
        config_data = list(filter(lambda x: x["name"] == app, config_data))

    list(map(clone_repositories, config_data))
    list(map(download_data, config_data))


def sync_applications(app=None):
    config_data = load_config()

    if app:
        config_data = list(filter(lambda x: x["name"] == app, config_data))

    list(map(upload_data, config_data))


def create_new_workspace(app=None):
    config_data = load_config()

    if app:
        config_data = list(filter(lambda x: x["name"] == app, config_data))

    list(map(create_template, config_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Application to sync my workspace data using config files'
    )

    parser.add_argument(
        "--setup",
        help="setup all the active workspaces",
    )
    parser.add_argument(
        "--sync",
        help="sync all the active workspaces",
    )
    parser.add_argument(
        "--add",
        help="creates a specific path of workspace using structure",
    )

    args = vars(parser.parse_args())

    if args["setup"]:
        setup_applications(args["setup"])
    if args["sync"]:
        sync_applications(args["sync"])
    if args["add"]:
        create_new_workspace(args["add"])

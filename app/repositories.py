import os


def clone_repository(url, target):
    os.system("git clone {} {} > /dev/null 2>&1".format(url, target))


def clone_repositories(config_data):
    """
    clones the repositories as specified in the config data
    """

    workspace_name = config_data["name"]
    workspace_path = config_data["workspace_path"]

    repositories = config_data["repositories"]

    for repository in repositories:
        clone_name = repository["clone_name"]
        clone_path = repository["clone_path"]
        repo_url = repository["repo_url"]

        clone_location = os.path.join(
            workspace_path, workspace_name, clone_path, clone_name
        )

        if not os.path.exists(clone_location):
            print("Cloning repository {} to path {}".format(
                repo_url, clone_location
            ))

            clone_repository(repo_url, clone_location)
            continue

        print("Skipping {} as path already present".format(
            repo_url
        ))

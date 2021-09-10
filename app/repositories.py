import os


def clone_repository(url, target):
    os.system("git clone {} {} > /dev/null 2>&1".format(url, target))


def clone_repositories(config_data):
    """
    clones the repositories as specified in the config data
    """

    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]

    codes = config_data["codes"]

    for source, apps in codes.items():
        for app_type, repo_urls in apps.items():
            for repo_url in repo_urls:
                repo_name = repo_url.split("/")[-1].split(".")[0].lower()\
                    .replace("_", "-")
                clone_path = os.path.join(
                    target_path, folder_name, "codes",
                    app_type, source, repo_name
                )

                if not os.path.exists(clone_path):
                    print("Cloning {} repository {}".format(app_type,
                                                            repo_name))
                    os.system("mkdir -p {}".format(clone_path))
                    clone_repository(repo_url, clone_path)
                    continue

                print("Skipping {} as path already present".format(
                    repo_name
                ))

import os
import re


def clone_repository(url, target):
    os.system("git clone {} {} > /dev/null 2>&1".format(url, target))


def get_repo_name(repo_url):
    """
    handling wierd case when your git repo name has dots in it
    plus another weird scenario when your repository name is
    xyz.github.io.git
    """

    last_part = repo_url.split("/")[-1]
    pattern = re.compile(r'(.*?)\.git$')

    try:
        repo_name = pattern.search(last_part).group(1)
    except Exception:
        repo_name = last_part

    return repo_name.lower().replace("_", "-")


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
                repo_name = get_repo_name(repo_url)
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

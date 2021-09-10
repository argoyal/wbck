import os
import shutil


def create_template(config_data):
    """
    creates the workspace in specific path
    """

    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]

    src_path = "structure"
    dst_path = os.path.join(target_path, folder_name)

    if os.path.exists(dst_path):
        return

    print("Creating workspace {}".format(folder_name))
    shutil.copytree(src_path, dst_path)

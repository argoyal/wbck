import os
import shutil
import zipfile
from .utils import zipdir


def local_upload_data(config_data):
    """
    uploads the data locally to a path specified in the configurations
    """

    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]
    settings = config_data['workplace_settings']['local']
    tmp_path = os.path.join(target_path, folder_name, 'tmp')

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    backup_folder = config_data["workplace_settings"]["local"]["backup_folder"]

    if not os.path.exists(backup_folder):
        raise FileNotFoundError(f"{backup_folder} does not exist")

    print(f"Creating temporary path {tmp_path}")
    if not os.path.exists(tmp_path):
        os.system("mkdir -p {}".format(tmp_path))

    for folder in settings["folders_to_maintain"]:
        src_path = os.path.join(target_path, folder_name, folder)
        dst_path = os.path.join(tmp_path, folder)

        if os.path.exists(dst_path):
            continue

        print(f"Copying {src_path} to tmp location")
        shutil.copytree(src_path, dst_path)

    zip_name = "{}.zip".format(folder_name)

    print(f"Generating zip file {zip_name}")
    zipf = zipfile.ZipFile(
        zip_name, 'w', zipfile.ZIP_DEFLATED
    )
    zipdir(tmp_path, zipf, settings['files_to_ignore'])
    zipf.close()

    print("======================> Uploading file {} to folder {}".format(
        zip_name, backup_folder))

    shutil.copy(zip_name, backup_folder)

    os.remove(zip_name)
    shutil.rmtree(tmp_path)


def local_download_data(config_data):
    """
    downloads from the local path
    """
    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]
    settings = config_data['workplace_settings']['local']
    backup_folder = config_data['workplace_settings']['local']['backup_folder']

    zip_name = "{}.zip".format(folder_name)

    print("======================> Downloading file {} from folder {}".format(
        zip_name, backup_folder))

    backup_path = os.path.join(backup_folder, zip_name)

    shutil.copy(backup_path, zip_name)

    with zipfile.ZipFile(zip_name, 'r') as zip_ref:
        zip_ref.extractall(os.path.join(target_path, folder_name))

    for folder in settings["folders_to_maintain"]:
        tmp_path = os.path.join(target_path, folder_name, 'tmp')
        dst_path = os.path.join(target_path, folder_name, folder)
        src_path = os.path.join(tmp_path, folder)

        if not os.path.exists(src_path):
            os.system("mkdir -p {}".format(src_path))

        if os.path.exists(dst_path):
            continue

        shutil.copytree(src_path, dst_path)

    os.remove(zip_name)
    shutil.rmtree(tmp_path)

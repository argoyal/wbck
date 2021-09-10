import os
import boto3
import shutil
import zipfile
from .utils import zipdir


BUCKET_NAME = os.environ.get("BUCKET_NAME")
AWS_KEY = os.environ.get("AWS_KEY")
AWS_SECRET = os.environ.get("AWS_SECRET")


def download_data(config_data):
    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]
    settings = config_data['workplace_settings']['s3']

    zip_name = "{}.zip".format(folder_name)

    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )

    print("======================> Downloading file {} from bucket {}".format(
        zip_name, BUCKET_NAME))
    s3.download_file(BUCKET_NAME, zip_name, zip_name)

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


def upload_data(config_data):
    folder_name = config_data["name"]
    target_path = os.getenv("HOME") if not config_data["target_path"] else\
        config_data["target_path"]
    settings = config_data['workplace_settings']['s3']
    tmp_path = os.path.join(target_path, folder_name, 'tmp')

    if not os.path.exists(tmp_path):
        os.system("mkdir -p {}".format(tmp_path))

    for folder in settings["folders_to_maintain"]:
        src_path = os.path.join(target_path, folder_name, folder)
        dst_path = os.path.join(tmp_path, folder)

        if os.path.exists(dst_path):
            continue

        shutil.copytree(src_path, dst_path)

    zip_name = "{}.zip".format(folder_name)

    zipf = zipfile.ZipFile(
        zip_name, 'w', zipfile.ZIP_DEFLATED
    )
    zipdir(tmp_path, zipf, settings['files_to_ignore'])
    zipf.close()

    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )

    print("======================> Uploading file {} to bucket {}".format(
        zip_name, BUCKET_NAME))

    s3.upload_file(zip_name, BUCKET_NAME, zip_name)

    os.remove(zip_name)
    shutil.rmtree(tmp_path)

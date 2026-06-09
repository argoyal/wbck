import os
import zipfile
import boto3
from datetime import datetime

from .base import BaseSource


class AwsSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        s3_creds = self.source_credentials.get("s3", {})
        self.AWS_KEY = s3_creds.get("aws_key", "")
        self.AWS_SECRET = s3_creds.get("aws_secret", "")
        self.AWS_PROFILE = s3_creds.get("aws_profile", "")
        self.BUCKET_NAME = s3_creds.get("root_path", "")

        # workspace-level archival keys (enabled=0 flow)
        self.s3_key = "{}/{}".format(self.workspace_name, self.zip_name)
        self.archive_s3_key = "{}/{}".format(self.workspace_name, self.archive_zip_name)

    def _get_s3_client(self):
        if self.AWS_PROFILE:
            return boto3.Session(profile_name=self.AWS_PROFILE).client('s3')
        if self.AWS_KEY and self.AWS_SECRET:
            return boto3.client(
                's3',
                aws_access_key_id=self.AWS_KEY,
                aws_secret_access_key=self.AWS_SECRET
            )
        raise ValueError(
            "S3 configuration requires either 'aws_profile' or both 'aws_key' and 'aws_secret'."
        )

    def _s3_key_for_path(self, path_entry):
        """Returns the S3 key to use for backup (today's date)."""
        if path_entry.get("backup_location"):
            return path_entry["backup_location"]
        date = datetime.now().date().isoformat()
        return "{}/{}-{}.zip".format(self.workspace_name, path_entry["folder_name"], date)

    def _latest_s3_key_for_path(self, path_entry):
        """Finds the latest backup S3 key for a path entry by listing objects."""
        if path_entry.get("backup_location"):
            return path_entry["backup_location"]
        prefix = "{}/{}-".format(self.workspace_name, path_entry["folder_name"])
        s3 = self._get_s3_client()
        resp = s3.list_objects_v2(Bucket=self.BUCKET_NAME, Prefix=prefix)
        objects = resp.get("Contents", [])
        zips = sorted(
            [obj["Key"] for obj in objects if obj["Key"].endswith(".zip")]
        )
        if not zips:
            raise FileNotFoundError(
                "No backup found for '{}' in s3://{}/{}".format(
                    path_entry["folder_name"], self.BUCKET_NAME, prefix))
        return zips[-1]

    # ------------------------------------------------------------------ #
    # Path-level methods
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """Zips the path and uploads to S3. Returns ('success'|'failed', note)."""
        zip_name = self._make_path_zip(path_entry, paths_to_exclude)
        key = self._s3_key_for_path(path_entry)

        print("======================> Uploading {} to s3://{}/{}".format(
            zip_name, self.BUCKET_NAME, key))

        try:
            s3 = self._get_s3_client()
            s3.upload_file(zip_name, self.BUCKET_NAME, key)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        return "success", ""

    def restore_path(self, path_entry, keep_remote=False):
        """Downloads the latest backup zip from S3, extracts it, then deletes it unless keep_remote."""
        key = self._latest_s3_key_for_path(path_entry)
        zip_name = os.path.basename(key)

        print("======================> Downloading s3://{}/{} to {}".format(
            self.BUCKET_NAME, key, zip_name))

        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, key, zip_name)

        try:
            parent_dir = os.path.dirname(path_entry.get("folder_path", ""))
            target = os.path.join(self.workspace_path, self.workspace_name, parent_dir)
            os.makedirs(target, exist_ok=True)
            with zipfile.ZipFile(zip_name, 'r') as zf:
                zf.extractall(target)
            if not keep_remote:
                print("======================> Deleting s3://{}/{}".format(self.BUCKET_NAME, key))
                s3.delete_object(Bucket=self.BUCKET_NAME, Key=key)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        return "success"

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow)
    # ------------------------------------------------------------------ #

    def archive_data(self):
        self.generate_full_compressed_data()
        print("======================> Uploading archive {} to bucket {}".format(
            self.archive_zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.upload_file(self.archive_zip_name, self.BUCKET_NAME, self.archive_s3_key)
        self.perform_archive_cleanup()

    def backup_data(self):
        self.generate_compressed_data()
        print("======================> Uploading file {} to bucket {}".format(
            self.zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.upload_file(self.zip_name, self.BUCKET_NAME, self.s3_key)
        self.perform_cleanup()

    def restore_data(self):
        print("======================> Downloading file {} from bucket {}".format(
            self.zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, self.s3_key, self.zip_name)
        self.extract_from_compressed_data()
        self.perform_cleanup()

    def restore_archive_data(self, keep_remote=False):
        print("======================> Downloading archive {} from bucket {}".format(
            self.archive_zip_name, self.BUCKET_NAME))
        s3 = self._get_s3_client()
        s3.download_file(self.BUCKET_NAME, self.archive_s3_key, self.archive_zip_name)
        self.extract_from_archive_data()
        if not keep_remote:
            self.perform_archive_cleanup()

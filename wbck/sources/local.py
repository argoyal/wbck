import os
import shutil
import zipfile
from datetime import datetime

from .base import BaseSource


class LocalSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        local_creds = self.source_credentials.get("local", {})
        self.local_path = local_creds.get("root_path", "")

    def _dest_path_for_entry(self, path_entry):
        """Returns the full destination file path for a path entry."""
        if path_entry.get("backup_location"):
            return path_entry["backup_location"]
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}.zip".format(path_entry["folder_name"], date)
        return os.path.join(self.local_path, self.workspace_name, zip_name)

    # ------------------------------------------------------------------ #
    # Path-level methods
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """Zips the path and copies to local destination. Returns ('success'|'failed', note)."""
        # Only check local_path if we're using the default location
        if not path_entry.get("backup_location") and not os.path.exists(self.local_path):
            raise FileNotFoundError(f"Local backup root '{self.local_path}' does not exist")

        zip_name = self._make_path_zip(path_entry, paths_to_exclude)
        dest = self._dest_path_for_entry(path_entry)

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print("======================> Copying {} to {}".format(zip_name, dest))

        try:
            shutil.copy(zip_name, dest)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        return "success", ""

    def restore_path(self, path_entry, keep_remote=False):
        """Copies zip from local source, extracts it, then deletes the source zip unless keep_remote."""
        source_zip = self._dest_path_for_entry(path_entry)

        date = datetime.now().date().isoformat()
        local_zip = "{}-{}.zip".format(path_entry["folder_name"], date)

        print("======================> Copying {} to {}".format(source_zip, local_zip))
        shutil.copy(source_zip, local_zip)

        try:
            target = os.path.join(self.workspace_path, self.workspace_name)
            with zipfile.ZipFile(local_zip, 'r') as zf:
                zf.extractall(target)
            if not keep_remote:
                print("======================> Deleting source zip {}".format(source_zip))
                os.remove(source_zip)
        finally:
            if os.path.exists(local_zip):
                os.remove(local_zip)

        return "success"

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow)
    # ------------------------------------------------------------------ #

    def archive_data(self):
        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"{self.local_path} does not exist")
        self.generate_full_compressed_data()
        print("======================> Uploading archive {} to folder {}".format(
            self.archive_zip_name, self.local_path))
        shutil.copy(self.archive_zip_name, self.local_path)
        self.perform_archive_cleanup()

    def restore_archive_data(self, keep_remote=False):
        print("======================> Downloading archive {} from folder {}".format(
            self.archive_zip_name, self.local_path))
        archive_path = os.path.join(self.local_path, self.archive_zip_name)
        shutil.copy(archive_path, self.archive_zip_name)
        self.extract_from_archive_data()
        if not keep_remote:
            self.perform_archive_cleanup()

    def backup_data(self):
        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"{self.local_path} does not exist")
        self.generate_compressed_data()
        print("======================> Uploading file {} to folder {}".format(
            self.zip_name, self.local_path))
        shutil.copy(self.zip_name, self.local_path)
        self.perform_cleanup()

    def restore_data(self):
        print("======================> Downloading file {} from folder {}".format(
            self.zip_name, self.local_path))
        backup_path = os.path.join(self.local_path, self.zip_name)
        shutil.copy(backup_path, self.zip_name)
        self.extract_from_compressed_data()
        self.perform_cleanup()

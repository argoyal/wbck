import os
import shutil
import zipfile
from ..utils import zipdir
from .base import BaseSource


class LocalSource(BaseSource):

    def __init__(self, config_data):
        super().__init__(config_data)
        
        self.local_path = self.source_settings["local"]["local_path"]

    def backup_data(self):
        """
        backs up data to a local path specified in the configurations
        """

        if not os.path.exists(self.local_path):
            raise FileNotFoundError(f"{self.local_path} does not exist")

        self.generate_compressed_data()

        print("======================> Uploading file {} to folder {}".format(
            self.zip_name, self.local_path))

        shutil.copy(self.zip_name, self.local_path)

        self.perform_cleanup()

    def restore_data(self):
        """
        restores data from a local path specified in the configurations
        """

        print("======================> Downloading file {} from folder {}".format(
            self.zip_name, self.local_path))

        backup_path = os.path.join(self.local_path, self.zip_name)

        shutil.copy(backup_path, self.zip_name)

        self.extract_from_compressed_data()

        self.perform_cleanup()
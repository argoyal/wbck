import os
import shutil
import zipfile
from ..utils import zipdir
from datetime import datetime


class BaseSource(object):
    """
    This is the base source class serving as the base
    constract for all the other sources where from the backup
    or restoration needs to happen
    """

    def __init__(self, config_data):
        self.config_data = config_data
        self.source_settings = config_data["source_settings"]

        self.workspace_name = self.config_data["name"]
        self.workspace_path = os.getenv("HOME") if not config_data["workspace_path"] else \
            config_data["workspace_path"]
        
        self.zip_name = "{}-{}.zip".format(
            self.workspace_name,
            datetime.now().date().isoformat()
        )
        self.tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')

    def backup_data(self):
        raise NotImplementedError()
    
    def restore_data(self):
        raise NotImplementedError()
    
    def perform_cleanup(self):
        """
        performs cleanup of the artifacts generated during the backup process
        """

        os.remove(self.zip_name)
        shutil.rmtree(self.tmp_path)
    
    def generate_compressed_data(self):
        """
        generates the compressed version of the data to backup
        """

        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path)

        if not os.path.exists(self.tmp_path):
            os.system("mkdir -p {}".format(self.tmp_path))

        for folder in self.source_settings["folders_to_maintain"]:
            src_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            dst_path = os.path.join(self.tmp_path, folder)

            if os.path.exists(dst_path):
                continue

            print(f"Copying {src_path} to tmp location")
            shutil.copytree(src_path, dst_path)

        print(f"Generating zip file {self.zip_name}")
        zipf = zipfile.ZipFile(
            self.zip_name, 'w', zipfile.ZIP_DEFLATED
        )
        zipdir(self.tmp_path, zipf, self.source_settings['files_to_exclude'])
        zipf.close()

    def extract_from_compressed_data(self):
        """
        extracts the compressed version of the data to specific paths
        as per configuration
        """

        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(self.workspace_path, self.workspace_name))

        for folder in self.source_settings["folders_to_maintain"]:
            tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')
            dst_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            src_path = os.path.join(tmp_path, folder)

            if not os.path.exists(src_path):
                os.system("mkdir -p {}".format(src_path))

            if os.path.exists(dst_path):
                continue

            shutil.copytree(src_path, dst_path)
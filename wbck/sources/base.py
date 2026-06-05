import os
import shutil
import zipfile
from datetime import datetime

from ..utils import zipdir


class BaseSource(object):
    """
    Base class for all backup/restore sources.
    Workspace-level archival methods (archive_data, restore_archive_data) are
    preserved here for the enabled=0 archival flow.
    Path-level backup_path / restore_path are implemented by each subclass.
    """

    def __init__(self, config_data):
        self.config_data = config_data
        self.source_credentials = config_data.get("source_credentials", {})
        self.paths_to_exclude = config_data.get("paths_to_exclude", [])

        self.workspace_name = config_data["name"]
        self.workspace_path = (
            os.getenv("HOME")
            if not config_data["workspace_path"]
            else config_data["workspace_path"]
        )

        _today = datetime.now().date().isoformat()
        self.zip_name = "{}-{}.zip".format(self.workspace_name, _today)
        self.archive_zip_name = "{}-archive-{}.zip".format(self.workspace_name, _today)
        self.tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')

    # ------------------------------------------------------------------ #
    # Path-level interface (implemented by subclasses)
    # ------------------------------------------------------------------ #

    def backup_path(self, path_entry, paths_to_exclude):
        """
        Back up a single path entry.
        Returns (status, note) where status is 'success' | 'skipped' | 'failed'.
        """
        raise NotImplementedError()

    def restore_path(self, path_entry, keep_remote=False):
        """Restore a single path entry. Returns status string."""
        raise NotImplementedError()

    def dry_run_path(self, path_entry, paths_to_exclude):
        """
        Trial-zip every file in the path entry to surface per-file issues.
        Returns list of (relative_path, issue_description) tuples.
        """
        resolved = self._resolve_path(path_entry)

        if not os.path.exists(resolved):
            return [(resolved, "path does not exist")]

        issues = []
        tmp_zip = os.path.join(
            self.workspace_path,
            ".wbck-dryrun-{}.zip".format(path_entry["folder_name"]),
        )

        try:
            zipf = zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED)
            try:
                for root, dirs, files in os.walk(resolved):
                    rel_root = os.path.relpath(root, resolved)
                    dirs[:] = [
                        d for d in dirs
                        if d not in paths_to_exclude
                        and os.path.join(rel_root, d) not in paths_to_exclude
                    ]
                    for file in files:
                        rel_file = os.path.join(rel_root, file)
                        if file in paths_to_exclude or rel_file in paths_to_exclude:
                            continue
                        fpath = os.path.join(root, file)
                        arcname = os.path.relpath(fpath, os.path.join(resolved, '..'))
                        try:
                            zipf.write(fpath, arcname)
                        except Exception as e:
                            rel = os.path.relpath(fpath, resolved)
                            issues.append((rel, str(e)))
            finally:
                zipf.close()
        except Exception as e:
            issues.append((".", "failed to create zip: {}".format(e)))
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)

        return issues

    def dry_run_full_workspace(self):
        """
        Trial-zip the entire workspace directory (mirrors generate_full_compressed_data).
        Used for disabled workspaces where the real backup archives everything.
        Returns list of (relative_path, issue_description) tuples.
        """
        workspace_dir = os.path.join(self.workspace_path, self.workspace_name)

        if not os.path.exists(workspace_dir):
            return [(workspace_dir, "workspace directory does not exist")]

        issues = []
        tmp_zip = os.path.join(
            self.workspace_path,
            ".wbck-dryrun-full-{}.zip".format(self.workspace_name),
        )

        try:
            zipf = zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED)
            try:
                for root, dirs, files in os.walk(workspace_dir):
                    rel_root = os.path.relpath(root, workspace_dir)
                    dirs[:] = [
                        d for d in dirs
                        if d not in self.paths_to_exclude
                        and os.path.join(rel_root, d) not in self.paths_to_exclude
                    ]
                    for file in files:
                        rel_file = os.path.join(rel_root, file)
                        if file in self.paths_to_exclude or rel_file in self.paths_to_exclude:
                            continue
                        fpath = os.path.join(root, file)
                        arcname = os.path.relpath(fpath, os.path.join(workspace_dir, '..'))
                        try:
                            zipf.write(fpath, arcname)
                        except Exception as e:
                            rel = os.path.relpath(fpath, workspace_dir)
                            issues.append((rel, str(e)))
            finally:
                zipf.close()
        except Exception as e:
            issues.append((".", "failed to create zip: {}".format(e)))
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)

        return issues

    # ------------------------------------------------------------------ #
    # Path-level helpers
    # ------------------------------------------------------------------ #

    def _resolve_path(self, path_entry):
        """Returns the absolute on-disk path for a path_entry."""
        return os.path.join(
            self.workspace_path, self.workspace_name, path_entry["folder_path"]
        )

    def _make_path_zip(self, path_entry, paths_to_exclude):
        """
        Compresses path_entry's folder into a local zip file.
        Returns the local zip filename (in cwd).
        """
        resolved = self._resolve_path(path_entry)
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}.zip".format(path_entry["folder_name"], date)

        zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(resolved, zipf, ignore=paths_to_exclude)
        zipf.close()
        return zip_name

    # ------------------------------------------------------------------ #
    # Workspace-level archival methods (enabled=0 flow — unchanged)
    # ------------------------------------------------------------------ #

    def backup_data(self):
        raise NotImplementedError()

    def archive_data(self):
        raise NotImplementedError()

    def restore_data(self):
        raise NotImplementedError()

    def restore_archive_data(self, keep_remote=False):
        raise NotImplementedError()

    def perform_cleanup(self):
        os.remove(self.zip_name)
        shutil.rmtree(self.tmp_path)

    def perform_archive_cleanup(self):
        os.remove(self.archive_zip_name)

    def generate_compressed_data(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path)
        if not os.path.exists(self.tmp_path):
            os.system("mkdir -p {}".format(self.tmp_path))

        folders = self.config_data.get("source_settings", {}).get("folders_to_maintain", [])
        for folder in folders:
            src_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            dst_path = os.path.join(self.tmp_path, folder)
            if os.path.exists(dst_path):
                continue
            print(f"Copying {src_path} to tmp location")
            shutil.copytree(src_path, dst_path)

        print(f"Generating zip file {self.zip_name}")
        zipf = zipfile.ZipFile(self.zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(self.tmp_path, zipf, ignore=self.paths_to_exclude)
        zipf.close()

    def generate_full_compressed_data(self):
        workspace_dir = os.path.join(self.workspace_path, self.workspace_name)
        print(f"Generating full archive zip {self.archive_zip_name}")
        zipf = zipfile.ZipFile(self.archive_zip_name, 'w', zipfile.ZIP_DEFLATED)
        zipdir(workspace_dir, zipf, ignore=self.paths_to_exclude)
        zipf.close()

    def extract_from_archive_data(self):
        with zipfile.ZipFile(self.archive_zip_name, 'r') as zip_ref:
            zip_ref.extractall(self.workspace_path)

    def extract_from_compressed_data(self):
        with zipfile.ZipFile(self.zip_name, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(self.workspace_path, self.workspace_name))

        folders = self.config_data.get("source_settings", {}).get("folders_to_maintain", [])
        for folder in folders:
            tmp_path = os.path.join(self.workspace_path, self.workspace_name, 'tmp')
            dst_path = os.path.join(self.workspace_path, self.workspace_name, folder)
            src_path = os.path.join(tmp_path, folder)

            if not os.path.exists(src_path):
                os.system("mkdir -p {}".format(src_path))
            if os.path.exists(dst_path):
                continue
            shutil.copytree(src_path, dst_path)

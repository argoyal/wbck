import os
import select
import subprocess
import sys
from datetime import datetime

from .base import BaseSource

# Environment for non-interactive git commands that touch remotes.
# Prevents credential prompts on both HTTPS and SSH.
_GIT_REMOTE_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
}


def _prompt_with_timeout(seconds):
    """
    Waits up to `seconds` for a single keystroke on stdin.
    Returns the lowercase first character, or None on timeout.
    """
    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if ready:
        line = sys.stdin.readline().strip().lower()
        if line:
            return line[0]
    return None


def _is_binary(filepath):
    """Check if a file appears to be binary by looking for null bytes."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except (IOError, OSError):
        return True


class GitSource(BaseSource):

    def _parse_dirty_files(self, resolved, porcelain_output, paths_to_exclude=None):
        """
        Classify dirty files from git status --porcelain output.
        Returns (code_files, non_code_files) — each a list of repo-relative paths.
        Code = text files, non-code = binary/data files.
        Files matching paths_to_exclude are silently skipped.
        """
        exclude = set(paths_to_exclude or [])
        code_files = []
        non_code_files = []

        for line in porcelain_output.splitlines():
            if len(line) < 4:
                continue
            filepath = line[3:]
            # Handle renames: "old -> new"
            if ' -> ' in filepath:
                filepath = filepath.split(' -> ')[-1]

            # Skip if any path component matches an exclusion
            parts = filepath.split(os.sep)
            if any(p in exclude for p in parts):
                continue

            abs_path = os.path.join(resolved, filepath)

            # Deleted or missing: safe for code dump (no new binary data)
            if not os.path.exists(abs_path):
                code_files.append(filepath)
                continue

            # Untracked directory: check each file inside
            if os.path.isdir(abs_path):
                for root, dirs, files in os.walk(abs_path):
                    dirs[:] = [d for d in dirs if d not in exclude]
                    for f in files:
                        if f in exclude:
                            continue
                        fpath = os.path.join(root, f)
                        rel = os.path.relpath(fpath, resolved)
                        if _is_binary(fpath):
                            non_code_files.append(rel)
                        else:
                            code_files.append(rel)
                continue

            if _is_binary(abs_path):
                non_code_files.append(filepath)
            else:
                code_files.append(filepath)

        return code_files, non_code_files

    def _dump_code_to_branch(self, resolved, code_files):
        """
        Creates a local-dump-<timestamp> branch containing only the given code files,
        then pushes it to origin. If push fails (no permissions), falls back to
        zipping the changed files to S3/local.

        Returns (dump_branch, pushed) where pushed indicates if remote push succeeded.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dump_branch = "local-dump-{}".format(timestamp)

        # Unstage everything so only code files end up in the commit
        subprocess.run(["git", "-C", resolved, "reset"],
                       capture_output=True, text=True)

        # Stage only code files
        subprocess.run(["git", "-C", resolved, "add", "--"] + code_files,
                       capture_output=True, text=True, check=True)

        # Commit on the current branch temporarily
        subprocess.run(
            ["git", "-C", resolved, "commit", "-m",
             "wbck: local dump of uncommitted changes"],
            capture_output=True, text=True, check=True
        )

        # Create the dump branch at this commit, then rewind current branch
        try:
            subprocess.run(["git", "-C", resolved, "branch", dump_branch],
                           capture_output=True, text=True, check=True)
        finally:
            # Always rewind — keeps current branch and worktree as they were
            subprocess.run(["git", "-C", resolved, "reset", "HEAD~1"],
                           capture_output=True, text=True)

        # Try to push the dump branch to origin (non-interactive)
        push_result = subprocess.run(
            ["git", "-C", resolved, "push", "origin", dump_branch],
            capture_output=True, text=True, env=_GIT_REMOTE_ENV
        )
        pushed = push_result.returncode == 0

        return dump_branch, pushed

    @staticmethod
    def _dump_note(dump_branch, pushed, fallback_dest):
        if not dump_branch:
            return ""
        if pushed:
            return "pushed to {}".format(dump_branch)
        if fallback_dest:
            return "zip backed up to {}".format(fallback_dest)
        return "local branch only: {}".format(dump_branch)

    def _resolve_fallback_source(self):
        """Returns the fallback source name: default_source if set, else first non-git source."""
        default = self.config_data.get("default_source", "")
        if default and default != "git" and default in self.source_credentials:
            return default
        non_git = [src for src in self.source_credentials if src != "git"]
        return non_git[0] if non_git else None

    def _fallback_zip_to_backup(self, path_entry, code_files, dump_branch, config_path=None):
        """
        When git push fails, zip the changed code files and back them up
        via the fallback source. Updates the config to add the fallback source
        to the path_entry's backup_source list.
        """
        from .aws import AwsSource
        from .local import LocalSource

        fallback_source = self._resolve_fallback_source()
        if not fallback_source:
            return None

        resolved = self._resolve_path(path_entry)
        date = datetime.now().date().isoformat()
        zip_name = "{}-{}-{}.zip".format(path_entry["folder_name"], dump_branch, date)

        import zipfile
        zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        try:
            for f in code_files:
                fpath = os.path.join(resolved, f)
                if os.path.exists(fpath):
                    zipf.write(fpath, f)
        finally:
            zipf.close()

        try:
            if fallback_source == "s3":
                handler = AwsSource(self.config_data)
                s3 = handler._get_s3_client()
                key = "{}/{}/{}".format(
                    self.workspace_name, path_entry["folder_name"], zip_name)
                s3.upload_file(zip_name, handler.BUCKET_NAME, key)
                dest = "s3://{}/{}".format(handler.BUCKET_NAME, key)
            else:
                handler = LocalSource(self.config_data)
                dest_dir = os.path.join(
                    handler.local_path, self.workspace_name, path_entry["folder_name"])
                os.makedirs(dest_dir, exist_ok=True)
                import shutil
                dest = os.path.join(dest_dir, zip_name)
                shutil.copy(zip_name, dest)
        finally:
            if os.path.exists(zip_name):
                os.remove(zip_name)

        # Update config: add fallback source to this path's backup_source
        if config_path:
            self._update_config_with_fallback(config_path, path_entry, fallback_source)

        return "{} ({})".format(fallback_source, dest)

    @staticmethod
    def _update_config_with_fallback(config_path, path_entry, fallback_source):
        """Adds fallback_source to the path_entry's backup_source list in the config file."""
        import json
        with open(config_path, 'r') as f:
            config = json.load(f)

        for entry in config.get("paths_to_include", []):
            if entry["folder_name"] == path_entry["folder_name"]:
                sources = entry.get("backup_source", [])
                if fallback_source not in sources:
                    sources.append(fallback_source)
                    entry["backup_source"] = sources
                break

        with open(config_path, 'w') as f:
            json.dump(config, f, indent='\t')

    def _push_unpushed_commits(self, resolved, path_entry, config_path):
        """
        Checks for commits ahead of the remote tracking branch and pushes them.
        Returns a note string (empty if nothing to push or push succeeded).
        """
        # Check if there's an upstream configured
        upstream = subprocess.run(
            ["git", "-C", resolved, "rev-parse", "--abbrev-ref", "@{u}"],
            capture_output=True, text=True
        )
        if upstream.returncode != 0:
            # No upstream — try to push the current branch
            branch = subprocess.run(
                ["git", "-C", resolved, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True
            )
            branch_name = branch.stdout.strip()
            if not branch_name or branch_name == "HEAD":
                return ""
            push_result = subprocess.run(
                ["git", "-C", resolved, "push", "-u", "origin", branch_name],
                capture_output=True, text=True, env=_GIT_REMOTE_ENV
            )
            if push_result.returncode == 0:
                return "pushed branch '{}'".format(branch_name)
            return ""

        # Check how many commits ahead
        ahead = subprocess.run(
            ["git", "-C", resolved, "rev-list", "--count", "@{u}..HEAD"],
            capture_output=True, text=True
        )
        count = ahead.stdout.strip()
        if count == "0":
            return ""

        # Push current branch
        push_result = subprocess.run(
            ["git", "-C", resolved, "push"],
            capture_output=True, text=True, env=_GIT_REMOTE_ENV
        )
        if push_result.returncode == 0:
            print(
                "\n[{}] pushed {} unpushed commit(s)".format(
                    path_entry['folder_name'], count)
            )
            return "pushed {} commit(s)".format(count)

        # Push failed — fall back to zip if we have dirty commits worth saving
        print(
            "\n[{}] has {} unpushed commit(s) but push failed — "
            "falling back to zip backup".format(
                path_entry['folder_name'], count)
        )
        fallback = self._resolve_fallback_source()
        if not fallback:
            return "{} unpushed commit(s), push failed, no fallback".format(count)

        # Bundle the unpushed commits as a git bundle file and back up
        fallback_dest = self._fallback_bundle_to_backup(
            resolved, path_entry, config_path)
        if fallback_dest:
            return "{} unpushed commit(s) bundled to {}".format(count, fallback_dest)
        return "{} unpushed commit(s), push failed".format(count)

    def _fallback_bundle_to_backup(self, resolved, path_entry, config_path):
        """
        Creates a git bundle of unpushed commits and backs it up via fallback source.
        """
        from .aws import AwsSource
        from .local import LocalSource

        fallback_source = self._resolve_fallback_source()
        if not fallback_source:
            return None

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle_name = "{}-unpushed-{}.bundle".format(
            path_entry["folder_name"], timestamp)

        # Create bundle of commits not on the remote
        result = subprocess.run(
            ["git", "-C", resolved, "bundle", "create", bundle_name,
             "--not", "--remotes", "--all"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None

        bundle_path = os.path.join(resolved, bundle_name)
        try:
            if fallback_source == "s3":
                handler = AwsSource(self.config_data)
                s3 = handler._get_s3_client()
                key = "{}/{}/{}".format(
                    self.workspace_name, path_entry["folder_name"], bundle_name)
                s3.upload_file(bundle_path, handler.BUCKET_NAME, key)
                dest = "s3://{}/{}".format(handler.BUCKET_NAME, key)
            else:
                handler = LocalSource(self.config_data)
                dest_dir = os.path.join(
                    handler.local_path, self.workspace_name, path_entry["folder_name"])
                os.makedirs(dest_dir, exist_ok=True)
                import shutil
                dest = os.path.join(dest_dir, bundle_name)
                shutil.copy(bundle_path, dest)
        finally:
            if os.path.exists(bundle_path):
                os.remove(bundle_path)

        if config_path:
            self._update_config_with_fallback(config_path, path_entry, fallback_source)

        return "{} ({})".format(fallback_source, dest)

    def backup_path(self, path_entry, paths_to_exclude, config_path=None):
        """
        Checks if the repo is clean. If dirty:
        - Code (text) files are auto-committed to a local-dump-<ts> branch and pushed.
        - If push fails, falls back to zip backup via default_source.
        - Non-code (binary) files are flagged for the user to handle.
        Returns ('success'|'skipped', note).
        """
        resolved = self._resolve_path(path_entry)

        result = subprocess.run(
            ["git", "-C", resolved, "status", "--porcelain"],
            capture_output=True, text=True
        )
        is_clean = not result.stdout.strip()

        if is_clean:
            # Worktree is clean — check for unpushed commits
            push_note = self._push_unpushed_commits(resolved, path_entry, config_path)
            return "success", push_note

        code_files, non_code_files = self._parse_dirty_files(
            resolved, result.stdout, paths_to_exclude)

        dump_branch = None
        pushed = False
        fallback_dest = None
        if code_files:
            try:
                dump_branch, pushed = self._dump_code_to_branch(resolved, code_files)
                if pushed:
                    print(
                        "\n[{}] pushed {} code file(s) to branch '{}'".format(
                            path_entry['folder_name'], len(code_files), dump_branch)
                    )
                else:
                    print(
                        "\n[{}] created local branch '{}' but push failed — "
                        "falling back to zip backup".format(
                            path_entry['folder_name'], dump_branch)
                    )
                    fallback_dest = self._fallback_zip_to_backup(
                        path_entry, code_files, dump_branch, config_path)
                    if fallback_dest:
                        print(
                            "[{}] code backed up to {}".format(
                                path_entry['folder_name'], fallback_dest)
                        )
                    else:
                        print(
                            "[{}] no fallback source configured — "
                            "code only in local branch".format(path_entry['folder_name'])
                        )
            except subprocess.CalledProcessError as e:
                print(
                    "\n[{}] failed to create dump branch: {}".format(
                        path_entry['folder_name'], e.stderr.strip() if e.stderr else e)
                )

        # Also push any prior unpushed commits on the current branch
        unpushed_note = self._push_unpushed_commits(resolved, path_entry, config_path)

        if not non_code_files:
            dump_note = self._dump_note(dump_branch, pushed, fallback_dest)
            parts = [n for n in [dump_note, unpushed_note] if n]
            if parts:
                return "success", "; ".join(parts)
            return "skipped", "uncommitted changes"

        # Non-code files need user attention
        while True:
            print(
                "\n[{}] has {} non-code file(s) requiring attention:".format(
                    path_entry['folder_name'], len(non_code_files))
            )
            for f in non_code_files:
                print("    {}".format(f))
            print(
                "[R]etry / [C]ontinue (auto-continue in 60s): ",
                end="", flush=True
            )
            choice = _prompt_with_timeout(60)

            if choice == "r":
                # Re-check — user may have cleaned up non-code files
                result = subprocess.run(
                    ["git", "-C", resolved, "status", "--porcelain"],
                    capture_output=True, text=True
                )
                if not result.stdout.strip():
                    parts = [n for n in [self._dump_note(dump_branch, pushed, fallback_dest), unpushed_note] if n]
                    return "success", "; ".join(parts)
                _, non_code_files = self._parse_dirty_files(
                    resolved, result.stdout, paths_to_exclude)
                if not non_code_files:
                    parts = [n for n in [self._dump_note(dump_branch, pushed, fallback_dest), unpushed_note] if n]
                    return "success", "; ".join(parts)
                continue

            # Continue / timeout — skip with note
            parts = [n for n in [self._dump_note(dump_branch, pushed, fallback_dest), unpushed_note] if n]
            note = "{} non-code file(s) uncommitted".format(len(non_code_files))
            if parts:
                note = "{}; {}".format("; ".join(parts), note)
            return "skipped", note

    def check_remote(self, path_entry):
        """
        Checks whether the git remote is reachable and pushable.
        Returns (remote_url, reachable_error, push_error).
        reachable_error/push_error are None if the check passed.
        """
        resolved = self._resolve_path(path_entry)

        if not os.path.exists(resolved):
            return (path_entry.get("backup_location", "unknown"),
                    "path does not exist", None)

        # Get the remote URL
        result = subprocess.run(
            ["git", "-C", resolved, "remote", "get-url", "origin"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return ("no remote configured",
                    "git remote get-url origin failed", None)

        remote_url = result.stdout.strip()

        # ls-remote with a short timeout to check reachability (non-interactive)
        result = subprocess.run(
            ["git", "-C", resolved, "ls-remote", "--exit-code", "--heads", remote_url],
            capture_output=True, text=True, timeout=15, env=_GIT_REMOTE_ENV
        )
        if result.returncode != 0:
            error = result.stderr.strip() if result.stderr.strip() else "exit code {}".format(result.returncode)
            return (remote_url, error, None)

        # Check push access with a no-op dry-run push (non-interactive)
        result = subprocess.run(
            ["git", "-C", resolved, "push", "--dry-run", "origin", "HEAD:refs/heads/__wbck_push_test__"],
            capture_output=True, text=True, timeout=15, env=_GIT_REMOTE_ENV
        )
        if result.returncode != 0:
            push_error = result.stderr.strip() if result.stderr.strip() else "no push access"
            return (remote_url, None, push_error)

        return (remote_url, None, None)

    def _count_unpushed(self, resolved):
        """Returns the number of commits ahead of the upstream, or None if no upstream."""
        upstream = subprocess.run(
            ["git", "-C", resolved, "rev-parse", "--abbrev-ref", "@{u}"],
            capture_output=True, text=True
        )
        if upstream.returncode != 0:
            return None
        ahead = subprocess.run(
            ["git", "-C", resolved, "rev-list", "--count", "@{u}..HEAD"],
            capture_output=True, text=True
        )
        if ahead.returncode != 0:
            return None
        count = ahead.stdout.strip()
        return int(count) if count.isdigit() else None

    def dry_run_path(self, path_entry, paths_to_exclude):
        """
        Reports dirty files, unpushed commits, classified as code vs non-code.
        Returns list of (file_path, issue_description) tuples.
        """
        resolved = self._resolve_path(path_entry)

        if not os.path.exists(resolved):
            return [(resolved, "path does not exist")]

        issues = []

        # Check for unpushed commits
        unpushed = self._count_unpushed(resolved)
        if unpushed is None:
            issues.append(("no upstream", "branch has no remote tracking — will attempt push"))
        elif unpushed > 0:
            issues.append(("{} unpushed commit(s)".format(unpushed),
                           "will be pushed to remote"))

        result = subprocess.run(
            ["git", "-C", resolved, "status", "--porcelain"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            issues.append((".", "git status failed: {}".format(result.stderr.strip())))
            return issues

        if result.stdout.strip():
            code_files, non_code_files = self._parse_dirty_files(
                resolved, result.stdout, paths_to_exclude)

            if code_files:
                issues.append(("{} code file(s)".format(len(code_files)),
                               "will be auto-dumped to local-dump branch"))
            if non_code_files:
                issues.append(("{} non-code file(s)".format(len(non_code_files)),
                               "requires manual attention"))

        return issues

    def restore_path(self, path_entry, keep_remote=False):
        """
        Clones the repo if the path doesn't exist locally, otherwise pulls.
        No post-restore deletion (git remote is the source of truth).
        """
        resolved = self._resolve_path(path_entry)
        repo_url = path_entry["backup_location"]

        if os.path.exists(resolved):
            print(f"Pulling {repo_url} in {resolved}")
            subprocess.run(["git", "-C", resolved, "pull"], check=True)
        else:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            print(f"Cloning {repo_url} to {resolved}")
            subprocess.run(["git", "clone", repo_url, resolved], check=True)

        return "success"

import os
import select
import subprocess
import sys
from datetime import datetime

from .base import BaseSource


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
        Creates a local-dump-<timestamp> branch containing only the given code files.

        Strategy: unstage all → stage code files → commit → create branch →
        reset HEAD~1 (worktree stays dirty, current branch untouched).
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

        return dump_branch

    def backup_path(self, path_entry, paths_to_exclude):
        """
        Checks if the repo is clean. If dirty:
        - Code (text) files are auto-committed to a local-dump-<ts> branch.
        - Non-code (binary) files are flagged for the user to handle.
        Returns ('success'|'skipped', note).
        """
        resolved = self._resolve_path(path_entry)

        result = subprocess.run(
            ["git", "-C", resolved, "status", "--porcelain"],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            return "success", ""

        code_files, non_code_files = self._parse_dirty_files(
            resolved, result.stdout, paths_to_exclude)

        dump_branch = None
        if code_files:
            try:
                dump_branch = self._dump_code_to_branch(resolved, code_files)
                print(
                    "\n[{}] dumped {} code file(s) to branch '{}'".format(
                        path_entry['folder_name'], len(code_files), dump_branch)
                )
            except subprocess.CalledProcessError as e:
                print(
                    "\n[{}] failed to create dump branch: {}".format(
                        path_entry['folder_name'], e.stderr.strip() if e.stderr else e)
                )

        if not non_code_files:
            if dump_branch:
                return "success", "code dumped to {}".format(dump_branch)
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
                    note = "code dumped to {}".format(dump_branch) if dump_branch else ""
                    return "success", note
                _, non_code_files = self._parse_dirty_files(
                    resolved, result.stdout, paths_to_exclude)
                if not non_code_files:
                    note = "code dumped to {}".format(dump_branch) if dump_branch else ""
                    return "success", note
                continue

            # Continue / timeout — skip with note
            note = "{} non-code file(s) uncommitted".format(len(non_code_files))
            if dump_branch:
                note = "code dumped to {}; {}".format(dump_branch, note)
            return "skipped", note

    def dry_run_path(self, path_entry, paths_to_exclude):
        """
        Reports dirty files classified as code (auto-dump) vs non-code (needs attention).
        Returns list of (file_path, issue_description) tuples.
        """
        resolved = self._resolve_path(path_entry)

        if not os.path.exists(resolved):
            return [(resolved, "path does not exist")]

        result = subprocess.run(
            ["git", "-C", resolved, "status", "--porcelain"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return [(".", "git status failed: {}".format(result.stderr.strip()))]

        if not result.stdout.strip():
            return []

        code_files, non_code_files = self._parse_dirty_files(
            resolved, result.stdout, paths_to_exclude)

        issues = []
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

import os
import select
import subprocess
import sys

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


class GitSource(BaseSource):

    def backup_path(self, path_entry, paths_to_exclude):
        """
        Checks if the repo is clean. If dirty, prompts user to retry or continue.
        Auto-continues after 60 seconds. Returns ('success'|'skipped', note).
        Git backup is considered done when the repo is clean (remote has latest).
        """
        resolved = self._resolve_path(path_entry)

        while True:
            result = subprocess.run(
                ["git", "-C", resolved, "status", "--porcelain"],
                capture_output=True,
                text=True
            )
            if not result.stdout.strip():
                return "success", ""

            print(
                f"\n[{path_entry['folder_name']}] has uncommitted changes. "
                "[R]etry / [C]ontinue (auto-continue in 60s): ",
                end="",
                flush=True
            )
            choice = _prompt_with_timeout(60)

            if choice == "r":
                continue
            return "skipped", "uncommitted changes"

    def restore_path(self, path_entry):
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

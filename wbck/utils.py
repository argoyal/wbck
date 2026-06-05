import os
import zipfile
from datetime import datetime


def zipdir(path, ziph, ignore=[]):
    for root, dirs, files in os.walk(path):
        rel_root = os.path.relpath(root, path)
        dirs[:] = [
            d for d in dirs
            if d not in ignore and os.path.join(rel_root, d) not in ignore
        ]
        for file in files:
            rel_file = os.path.join(rel_root, file)
            if file in ignore or rel_file in ignore:
                continue
            ziph.write(
                os.path.join(root, file),
                os.path.relpath(
                    os.path.join(root, file),
                    os.path.join(path, '..')
                )
            )


def open_log(workspace_name):
    """Opens a new log file in /tmp, returns (file_handle, path)."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"/tmp/wbck-{workspace_name}-{timestamp}.log"
    return open(path, 'w'), path


def write_log(fh, folder_name, source, status, note=""):
    """Appends one line to the open log file handle."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{folder_name}] [{source}] {status}"
    if note:
        line += f" — {note}"
    fh.write(line + "\n")
    fh.flush()


def print_summary(results, workspace_name, log_path):
    """Prints terminal summary table (FAILED/SKIPPED only) and log path."""
    non_success = [(f, s, st, n) for f, s, st, n in results if st != "success"]

    total = len(results)
    failed = sum(1 for _, _, st, _ in results if st == "failed")
    skipped = sum(1 for _, _, st, _ in results if st == "skipped")

    print(f"\nBACKUP SUMMARY — {workspace_name}")
    print("─" * 57)

    if non_success:
        print(f" {'Folder':<20} {'Source':<8} {'Status':<9} Note")
        print("─" * 57)
        for folder, source, status, note in non_success:
            print(f" {folder:<20} {source:<8} {status.upper():<9} {note}")
        print("─" * 57)

    parts = [f"{total} paths processed"]
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if not failed and not skipped:
        parts.append("all succeeded")

    print(" · ".join(parts))
    print(f"\nFull log: {log_path}")


def print_dry_run_summary(results, workspace_name):
    """
    Prints the dry-run summary table.
    OK paths are listed first, then paths with issues below.
    results: list of (folder_name, source, issues, folder_path)
             where issues is list of (file, issue).
    """
    ok = []
    problems = []
    for entry in results:
        folder_name, source, issues, folder_path = entry
        if not issues:
            ok.append(entry)
        else:
            problems.append(entry)

    print(f"\nDRY-RUN SUMMARY — {workspace_name}")
    print("═" * 80)

    if ok:
        for folder_name, source, _, folder_path in ok:
            label = f"{folder_name} [{source}]"
            if folder_path:
                label += f"  ({folder_path})"
            print(f" {label}  OK")

    if problems:
        if ok:
            print()
        total_issues = 0
        for folder_name, source, issues, folder_path in problems:
            total_issues += len(issues)
            label = f"{folder_name} [{source}]"
            if folder_path:
                label += f"  ({folder_path})"
            print(f"\n {label}")
            print(f" {'File':<50} Issue")
            print(" " + "─" * 78)
            for fpath, issue in issues:
                print(f" {fpath:<50} {issue}")

    print("═" * 80)
    parts = [f"{len(results)} paths checked"]
    if problems:
        total_issues = sum(len(issues) for _, _, issues, _ in problems)
        parts.append(f"{len(problems)} with issues ({total_issues} files)")
    else:
        parts.append("no issues found")
    print(" · ".join(parts))


def print_unreachable_remotes(entries):
    """
    Prints a separate table of git repos whose remotes are unreachable.
    entries: list of (folder_name, remote_url, error, folder_path).
    """
    print(f"\nUNREACHABLE GIT REMOTES — consider switching to s3/local backup")
    print("═" * 100)
    print(f" {'Folder':<20} {'Path':<25} {'Remote':<35} Error")
    print("─" * 100)
    for folder_name, remote_url, error, folder_path in entries:
        print(f" {folder_name:<20} {folder_path:<25} {remote_url:<35} {error}")
    print("─" * 100)
    print(f" {len(entries)} remote(s) unreachable")


def print_unpushable_remotes(entries):
    """
    Prints a separate table of git repos where push access is denied.
    entries: list of (folder_name, remote_url, fallback_source, folder_path).
    """
    print(f"\nNO PUSH ACCESS — backup will fall back to zip")
    print("═" * 100)
    print(f" {'Folder':<20} {'Path':<25} {'Remote':<35} Fallback")
    print("─" * 100)
    for folder_name, remote_url, fallback, folder_path in entries:
        print(f" {folder_name:<20} {folder_path:<25} {remote_url:<35} {fallback}")
    print("─" * 100)
    print(f" {len(entries)} repo(s) without push access")

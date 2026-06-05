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
    results: list of (folder_name, source, issues) where issues is list of (file, issue).
    """
    print(f"\nDRY-RUN SUMMARY — {workspace_name}")
    print("═" * 80)

    total_paths = len(results)
    paths_with_issues = 0
    total_issues = 0

    for folder_name, source, issues in results:
        label = f"{folder_name} [{source}]"
        if not issues:
            print(f" {label:<40} OK")
            continue
        paths_with_issues += 1
        total_issues += len(issues)
        print(f"\n {label}")
        print(f" {'File':<50} Issue")
        print(" " + "─" * 78)
        for fpath, issue in issues:
            print(f" {fpath:<50} {issue}")

    print("═" * 80)
    parts = [f"{total_paths} paths checked"]
    if paths_with_issues:
        parts.append(f"{paths_with_issues} with issues ({total_issues} files)")
    else:
        parts.append("no issues found")
    print(" · ".join(parts))

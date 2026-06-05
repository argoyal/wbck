import zipfile
import os
from wbck.utils import zipdir, open_log, write_log, print_summary


def test_zipdir_excludes_directories(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = /usr")
    (tmp_path / "notes.txt").write_text("hello")

    zip_path = str(tmp_path / "test.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zipdir(str(tmp_path), zf, ignore=[".venv"])

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    assert not any(".venv" in n for n in names)
    assert any("notes.txt" in n for n in names)


def test_zipdir_excludes_files(tmp_path):
    (tmp_path / "secret.key").write_text("abc")
    (tmp_path / "notes.txt").write_text("hello")

    zip_path = str(tmp_path / "test.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zipdir(str(tmp_path), zf, ignore=["secret.key"])

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    assert not any("secret.key" in n for n in names)
    assert any("notes.txt" in n for n in names)


def test_write_log(tmp_path):
    log_path = str(tmp_path / "test.log")
    with open(log_path, 'w') as fh:
        write_log(fh, "notes", "s3", "SUCCESS", "")
        write_log(fh, "configs", "local", "FAILED", "Permission denied")

    content = open(log_path).read()
    assert "[notes] [s3] SUCCESS" in content
    assert "[configs] [local] FAILED — Permission denied" in content


def test_print_summary_omits_success_rows(capsys):
    results = [
        ("notes", "s3", "success", ""),
        ("configs", "local", "failed", "Permission denied"),
        ("repo", "git", "skipped", "uncommitted changes"),
    ]
    print_summary(results, "my-workspace", "/tmp/test.log")
    captured = capsys.readouterr()
    assert "configs" in captured.out
    assert "repo" in captured.out
    assert "notes" not in captured.out


def test_print_summary_counts(capsys):
    results = [
        ("a", "s3", "success", ""),
        ("b", "local", "failed", "err"),
        ("c", "git", "skipped", "dirty"),
    ]
    print_summary(results, "ws", "/tmp/test.log")
    captured = capsys.readouterr()
    assert "3 paths" in captured.out
    assert "1 failed" in captured.out
    assert "1 skipped" in captured.out

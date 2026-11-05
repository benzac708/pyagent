"""Tests for tools."""

from tools.bash import bash
from tools.check_backups import check_backups
from tools.check_disk import check_disk
from tools.check_services import check_services
from tools.edit_file import edit_file
from tools.list_files import list_files
from tools.list_runs import list_runs
from tools.read_file import read_file


def test_read_file_exists():
    result = read_file("fizzbuzz.js")
    assert "fizzbuzz" in result


def test_read_file_missing():
    result = read_file("nonexistent.txt")
    assert result.startswith("Error:")


def test_read_file_directory():
    result = read_file("agent")
    assert result.startswith("Error:")


def test_list_files():
    result = list_files(".")
    assert "[file]" in result or "[dir]" in result


def test_list_files_missing():
    result = list_files("nonexistent_dir")
    assert result.startswith("Error:")


def test_bash_echo():
    result = bash("echo hello")
    assert "hello" in result


def test_bash_timeout():
    result = bash("sleep 10", timeout=1)
    assert "timed out" in result


def test_bash_error():
    result = bash("false")
    assert "exit code" in result


def test_edit_file(tmp_path):
    path = str(tmp_path / "test.txt")
    result = edit_file(path, "hello world")
    assert "Successfully" in result
    assert open(path).read() == "hello world"


def test_edit_file_overwrite(tmp_path):
    path = str(tmp_path / "test.txt")
    edit_file(path, "first")
    edit_file(path, "second")
    assert open(path).read() == "second"


def test_check_disk():
    result = check_disk("/")
    assert "used_pct=" in result


def test_check_disk_bad_path():
    result = check_disk("/nonexistent-path-xyz")
    assert result.startswith("Error:")


def test_check_backups_exists():
    result = check_backups("README.md")
    assert "exists=true" in result


def test_check_backups_missing():
    result = check_backups("no-such-file-xyz.md")
    assert "exists=false" in result


def test_check_services_unknown():
    result = check_services(["definitely-not-a-real-service-xyz"])
    assert "definitely-not-a-real-service-xyz" in result


def test_list_runs_returns_string():
    result = list_runs(2)
    assert isinstance(result, str)


def test_read_file_blocks_secrets():
    result = read_file(".env")
    assert result.startswith("Error:")
    assert "not allowed" in result


def test_check_health_bad_url():
    from tools.check_health import check_health

    result = check_health("http://127.0.0.1:1/health")
    assert "unhealthy" in result

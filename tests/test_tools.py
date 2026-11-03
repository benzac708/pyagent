"""Tests for tools."""

from tools.bash import bash
from tools.edit_file import edit_file
from tools.list_files import list_files
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


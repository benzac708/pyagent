"""Security: secrets must not be readable by agent tools."""

from tools.bash import _redact
from tools.read_file import _is_sensitive


def test_read_file_blocks_env():
    assert _is_sensitive(".env") is True
    assert _is_sensitive("/app/.env") is True
    assert _is_sensitive(".env.local") is True


def test_read_file_blocks_keys_and_secrets():
    assert _is_sensitive("server.pem") is True
    assert _is_sensitive("id_rsa") is True
    assert _is_sensitive("credentials.json") is True
    assert _is_sensitive("my_secret.txt") is True


def test_read_file_allows_normal_files():
    assert _is_sensitive("fizzbuzz.js") is False
    assert _is_sensitive("README.md") is False
    assert _is_sensitive("agent/config.py") is False


def test_bash_redacts_secret():
    import os

    os.environ["API_KEY"] = "supersecret123"
    # reload module-level list
    import tools.bash as b

    b._SECRET_VALUES[:] = ["supersecret123"]
    assert _redact("the key is supersecret123 here") == "the key is [REDACTED] here"
    assert _redact("no secret here") == "no secret here"


def test_read_file_returns_error_for_sensitive():
    from tools.read_file import read_file

    assert read_file(".env").startswith("Error:")

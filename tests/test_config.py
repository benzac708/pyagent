"""Tests for config."""

from agent.config import has_fallback


def test_has_fallback():
    # With .env configured, fallback should be available
    assert has_fallback() is True

"""Pytest configuration.

The API tests need the web stack (fastapi, sqlalchemy, httpx). The language and
SRS tests do not, so they are skipped rather than failed when a bare
environment is all that is available.
"""

from __future__ import annotations

import importlib.util

import pytest


def _missing(module: str) -> bool:
    return importlib.util.find_spec(module) is None


def pytest_collection_modifyitems(config, items) -> None:  # noqa: ARG001
    if not (_missing("fastapi") or _missing("sqlalchemy")):
        return
    skip = pytest.mark.skip(reason="web dependencies not installed")
    for item in items:
        if "test_api" in item.nodeid:
            item.add_marker(skip)

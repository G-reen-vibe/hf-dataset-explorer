"""Pytest configuration and fixtures."""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark test as end-to-end (requires network)")


def pytest_addoption(parser):
    parser.addoption("--run-e2e", action="store_true", default=False,
                     help="run end-to-end tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-e2e"):
        skip_marker = pytest.mark.skip(reason="need --run-e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_marker)

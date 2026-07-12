"""End-to-end tests against the live HuggingFace API.

These tests hit the real HuggingFace Hub API. They are skipped by default
to avoid network calls during unit testing, but can be run with:

    pytest tests/test_e2e_api.py -v --run-e2e
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.hf_client import HFError, get_client


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark test as end-to-end (requires network)")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-e2e"):
        skip_marker = pytest.mark.skip(reason="need --run-e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_marker)


def pytest_addoption(parser):
    parser.addoption("--run-e2e", action="store_true", default=False,
                     help="run end-to-end tests")


@pytest.fixture
def client():
    return get_client("")


@pytest.mark.e2e
class TestLiveAPI:
    def test_list_datasets_returns_results(self, client):
        """Verify list_datasets returns at least one dataset."""
        results = client.list_datasets(limit=5)
        assert isinstance(results, list)
        assert len(results) > 0
        # Each result should have an id
        for ds in results:
            assert "id" in ds

    def test_list_datasets_search(self, client):
        """Verify search returns relevant results."""
        results = client.list_datasets(search="mnist", limit=5)
        assert len(results) > 0
        # At least one result should mention mnist in the id
        ids = [d.get("id", "").lower() for d in results]
        assert any("mnist" in i for i in ids)

    def test_get_dataset_real_id(self, client):
        """Verify we can fetch a known dataset."""
        ds = client.get_dataset("HuggingFaceH4/no_robots")
        assert ds["id"] == "HuggingFaceH4/no_robots"
        assert ds.get("downloads", 0) >= 0
        assert ds.get("likes", 0) >= 0
        # Should have tags
        assert isinstance(ds.get("tags"), list)
        assert len(ds["tags"]) > 0

    def test_get_dataset_404(self, client):
        """Verify an unknown dataset raises HFError."""
        with pytest.raises(HFError) as exc_info:
            # Use an obviously-invalid ID that won't exist
            client.get_dataset("___nonexistent_user_xyz___/no_such_dataset_abc123")
        # HF may return 401, 404, or 422 for invalid IDs depending on the dataset
        assert exc_info.value.status in (401, 404, 422, 500)

    def test_get_parquet_listing(self, client):
        """Verify parquet listing for a parquet dataset."""
        listing = client.get_parquet_listing("HuggingFaceH4/no_robots")
        assert isinstance(listing, dict)
        # Should have at least one config
        assert len(listing) >= 1
        # First config should have splits
        first_config = next(iter(listing.keys()))
        splits = listing[first_config]
        assert isinstance(splits, dict)
        assert len(splits) >= 1

    def test_get_rows(self, client):
        """Verify we can fetch rows from the rows API."""
        rows = client.get_rows("HuggingFaceH4/no_robots", "default", "train",
                               offset=0, length=5)
        assert isinstance(rows, dict)
        # Should have features and rows
        assert "features" in rows
        assert "rows" in rows
        assert len(rows["rows"]) > 0

    def test_get_trending(self, client):
        """Verify get_trending helper works."""
        results = client.get_trending(limit=10)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_get_most_downloaded(self, client):
        """Verify get_most_downloaded helper works."""
        results = client.get_most_downloaded(limit=10)
        assert isinstance(results, list)
        assert len(results) > 0
        # Results should be sorted by downloads descending
        downloads = [d.get("downloads", 0) for d in results]
        assert downloads == sorted(downloads, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-e2e"])

"""Unit tests for the HuggingFace API client (offline, no network calls)."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.hf_client import (
    HFClient,
    HFError,
    categorize_tag,
    parse_tags,
    TASK_CATEGORIES,
    MODALITIES,
    SIZE_CATEGORIES,
    LICENSES,
    FORMATS,
)


class TestTagCategorization:
    def test_task_category(self):
        assert categorize_tag("task_categories:text-generation") == "task"
        assert categorize_tag("task_categories:image-classification") == "task"

    def test_modality(self):
        assert categorize_tag("modality:text") == "modality"
        assert categorize_tag("modality:audio") == "modality"

    def test_size_category(self):
        assert categorize_tag("size_categories:1K<n<10K") == "size"
        assert categorize_tag("size_categories:n>1T") == "size"

    def test_language(self):
        assert categorize_tag("language:en") == "language"
        assert categorize_tag("language:zh") == "language"

    def test_license(self):
        assert categorize_tag("license:mit") == "license"
        assert categorize_tag("license:apache-2.0") == "license"

    def test_format(self):
        assert categorize_tag("format:parquet") == "format"
        assert categorize_tag("format:json") == "format"

    def test_uncategorized(self):
        assert categorize_tag("library:datasets") == "library"
        assert categorize_tag("region:us") == "region"
        assert categorize_tag("arxiv:2203.02155") == "arxiv"
        assert categorize_tag("unknown-tag") == ""


class TestParseTags:
    def test_group_by_category(self):
        tags = [
            "task_categories:text-generation",
            "modality:text",
            "language:en",
            "license:mit",
            "library:datasets",
        ]
        parsed = parse_tags(tags)
        assert "task" in parsed
        assert "modality" in parsed
        assert "language" in parsed
        assert "license" in parsed
        assert "library" in parsed
        assert "task_categories:text-generation" in parsed["task"]

    def test_empty(self):
        assert parse_tags([]) == {}

    def test_none(self):
        assert parse_tags(None) == {}


class TestTagTaxonomy:
    def test_all_task_categories_have_prefix(self):
        for t in TASK_CATEGORIES:
            assert t.startswith("task_categories:")

    def test_all_modalities_have_prefix(self):
        for t in MODALITIES:
            assert t.startswith("modality:")

    def test_all_size_categories_have_prefix(self):
        for t in SIZE_CATEGORIES:
            assert t.startswith("size_categories:")

    def test_all_licenses_have_prefix(self):
        for t in LICENSES:
            assert t.startswith("license:")

    def test_all_formats_have_prefix(self):
        for t in FORMATS:
            assert t.startswith("format:")


class TestHFClient:
    """Test the HFClient class with mocked HTTP responses."""

    def test_init_with_token(self):
        client = HFClient(token="hf_test_token_123")
        assert client.token == "hf_test_token_123"
        assert client._session.headers["Authorization"] == "Bearer hf_test_token_123"

    def test_init_without_token(self):
        client = HFClient()
        assert client.token == ""
        assert "Authorization" not in client._session.headers

    def test_init_strips_whitespace(self):
        client = HFClient(token="  hf_test_token_123  ")
        assert client.token == "hf_test_token_123"

    def test_get_404_raises_hferror(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        mock_resp.text = "Not found"
        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(HFError) as exc_info:
                client._get("/datasets/nonexistent")
            assert exc_info.value.status == 404

    def test_get_401_raises_hferror(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.ok = False
        mock_resp.text = "Unauthorized"
        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(HFError) as exc_info:
                client._get("/datasets/whatever")
            assert exc_info.value.status == 401

    def test_get_429_raises_hferror(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.ok = False
        mock_resp.text = "Rate limit"
        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(HFError) as exc_info:
                client._get("/datasets/whatever")
            assert exc_info.value.status == 429

    def test_get_network_error_raises_hferror(self):
        import requests
        client = HFClient()
        with patch.object(client._session, "get",
                          side_effect=requests.ConnectionError("Network down")):
            with pytest.raises(HFError) as exc_info:
                client._get("/datasets/whatever")
            assert "Network error" in str(exc_info.value)

    def test_list_datasets_builds_params(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = [{"id": "test/dataset"}]
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.list_datasets(
                search="mnist", author="huggingface",
                tags=["task_categories:text-generation"],
                sort="downloads", direction=-1, limit=10, offset=0,
            )
            assert result == [{"id": "test/dataset"}]
            # Verify params
            call_kwargs = mock_get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            assert params["search"] == "mnist"
            assert params["author"] == "huggingface"
            assert params["limit"] == 10
            assert params["sort"] == "downloads"
            assert params["direction"] == -1

    def test_list_datasets_normalizes_legacy_sort(self):
        """Verify legacy sort names are normalized to API canonical names."""
        from api.hf_client import clear_cache
        clear_cache()  # ensure no cached responses interfere
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = []
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            # 'trending' should be normalized to 'downloads'
            client.list_datasets(sort="trending", limit=5)
            call_args = mock_get.call_args
            assert call_args is not None, "session.get was not called"
            params = call_args.kwargs.get("params") or call_args[1].get("params")
            assert params["sort"] == "downloads"

            # 'created' should be normalized to 'createdAt'
            clear_cache()
            client.list_datasets(sort="created", limit=5)
            call_args = mock_get.call_args
            assert call_args is not None
            params = call_args.kwargs.get("params") or call_args[1].get("params")
            assert params["sort"] == "createdAt"

            # 'modified' should be normalized to 'lastModified'
            clear_cache()
            client.list_datasets(sort="modified", limit=5)
            call_args = mock_get.call_args
            assert call_args is not None
            params = call_args.kwargs.get("params") or call_args[1].get("params")
            assert params["sort"] == "lastModified"

    def test_get_dataset_calls_correct_url(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "test/dataset"}
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            result = client.get_dataset("test/dataset")
            assert result == {"id": "test/dataset"}
            call_args = mock_get.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
            assert "test/dataset" in url

    def test_cache_key(self):
        key1 = HFClient._cache_key("https://example.com", {"a": 1, "b": 2})
        key2 = HFClient._cache_key("https://example.com", {"b": 2, "a": 1})
        # Same params in different order should produce same key
        assert key1 == key2

    def test_get_rows_builds_params(self):
        client = HFClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"rows": []}
        with patch.object(client._session, "get", return_value=mock_resp) as mock_get:
            client.get_rows("test/dataset", "default", "train", offset=10, length=50)
            call_kwargs = mock_get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
            assert params["config"] == "default"
            assert params["split"] == "train"
            assert params["offset"] == 10
            assert params["length"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

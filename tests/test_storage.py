"""Unit tests for local storage (favorites, history, settings)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Redirect the storage file to a temp directory for each test."""
    from core import paths, storage
    monkeypatch.setattr(paths, "app_dir", tmp_path)
    monkeypatch.setattr(paths, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(paths, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(paths, "storage_file", tmp_path / "storage.json")
    yield


class TestFavorites:
    def test_add_and_list(self):
        from core import storage
        ds = {"id": "test/dataset", "author": "test", "downloads": 100}
        assert storage.add_favorite(ds) is True
        favs = storage.list_favorites()
        assert len(favs) == 1
        assert favs[0]["id"] == "test/dataset"

    def test_add_duplicate_returns_false(self):
        from core import storage
        ds = {"id": "test/dataset"}
        storage.add_favorite(ds)
        assert storage.add_favorite(ds) is False
        assert len(storage.list_favorites()) == 1

    def test_is_favorite(self):
        from core import storage
        ds = {"id": "test/dataset"}
        storage.add_favorite(ds)
        assert storage.is_favorite("test/dataset") is True
        assert storage.is_favorite("other/dataset") is False

    def test_remove(self):
        from core import storage
        ds = {"id": "test/dataset"}
        storage.add_favorite(ds)
        assert storage.remove_favorite("test/dataset") is True
        assert storage.is_favorite("test/dataset") is False
        assert storage.remove_favorite("test/dataset") is False  # already removed

    def test_toggle(self):
        from core import storage
        ds = {"id": "test/dataset"}
        assert storage.toggle_favorite(ds) is True
        assert storage.is_favorite("test/dataset") is True
        assert storage.toggle_favorite(ds) is False
        assert storage.is_favorite("test/dataset") is False

    def test_persisted_to_disk(self):
        from core import storage
        ds = {"id": "test/dataset", "downloads": 42, "likes": 3}
        storage.add_favorite(ds)
        # The storage file should exist on disk
        from core import paths
        assert paths.storage_file.exists()
        with paths.storage_file.open() as f:
            data = json.load(f)
        assert "favorites" in data
        assert len(data["favorites"]) == 1
        assert data["favorites"][0]["id"] == "test/dataset"


class TestHistory:
    def test_add_and_list(self):
        from core import storage
        ds = {"id": "test/dataset"}
        storage.add_history(ds)
        hist = storage.list_history()
        assert len(hist) == 1
        assert hist[0]["id"] == "test/dataset"

    def test_most_recent_first(self):
        from core import storage
        storage.add_history({"id": "first"})
        storage.add_history({"id": "second"})
        storage.add_history({"id": "third"})
        hist = storage.list_history()
        assert [h["id"] for h in hist] == ["third", "second", "first"]

    def test_no_duplicates(self):
        from core import storage
        storage.add_history({"id": "ds1"})
        storage.add_history({"id": "ds2"})
        storage.add_history({"id": "ds1"})  # Re-add
        hist = storage.list_history()
        assert len(hist) == 2
        assert hist[0]["id"] == "ds1"  # Now at the front

    def test_respects_limit(self):
        from core import storage
        storage.set_setting("history_limit", 5)
        for i in range(10):
            storage.add_history({"id": f"ds{i}"})
        hist = storage.list_history()
        assert len(hist) == 5
        # Most recent should be first
        assert hist[0]["id"] == "ds9"

    def test_clear(self):
        from core import storage
        storage.add_history({"id": "ds1"})
        storage.add_history({"id": "ds2"})
        storage.clear_history()
        assert storage.list_history() == []


class TestSettings:
    def test_defaults(self):
        from core import storage
        settings = storage.get_settings()
        assert "api_token" in settings
        assert "theme_mode" in settings
        assert settings["api_token"] == ""
        assert settings["theme_mode"] == "dark"
        assert settings["history_limit"] == 50

    def test_set_and_get(self):
        from core import storage
        storage.set_setting("api_token", "hf_test_token")
        assert storage.get_setting("api_token") == "hf_test_token"
        storage.set_setting("theme_mode", "light")
        assert storage.get_setting("theme_mode") == "light"

    def test_get_with_default(self):
        from core import storage
        assert storage.get_setting("nonexistent_key", "default_val") == "default_val"

    def test_persisted(self):
        from core import storage, paths
        storage.set_setting("api_token", "hf_persist_test")
        # Reload from disk by re-reading the file
        with paths.storage_file.open() as f:
            data = json.load(f)
        assert data["settings"]["api_token"] == "hf_persist_test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

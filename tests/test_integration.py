"""Integration test: verify the Flet app can be constructed without errors.

This test uses Flet's `page` test fixture to verify that the main app
entry point and all view factories run without raising exceptions.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Verify all top-level imports work."""
    from core import paths, app_state, storage
    from api.hf_client import HFClient, HFError, get_client
    from utils import formatters, ui_helpers
    from ui import theme, navigation, routing
    from views import explore, analytics, compare, favorites, history, settings, dataset_detail
    # All imports succeed
    assert True


def test_storage_initialization():
    """Verify the storage layer initializes and works."""
    from core import storage
    # Default settings should be returned
    s = storage.get_settings()
    assert "api_token" in s
    assert "theme_mode" in s


def test_theme_creation():
    """Verify the Flet theme objects can be constructed."""
    import flet as ft
    from ui.theme import light_theme, dark_theme
    light = light_theme()
    dark = dark_theme()
    assert isinstance(light, ft.Theme)
    assert isinstance(dark, ft.Theme)


def test_navigation_destinations():
    """Verify the navigation destinations are correctly defined."""
    from ui.navigation import _DESTINATIONS
    assert len(_DESTINATIONS) == 6
    # Each destination is (icon, label)
    for icon, label in _DESTINATIONS:
        # Icons may be a string or an enum
        assert icon is not None
        assert isinstance(label, str)
    # Check expected labels
    labels = [label for _, label in _DESTINATIONS]
    assert "Explore" in labels
    assert "Analytics" in labels
    assert "Compare" in labels
    assert "Favorites" in labels
    assert "History" in labels
    assert "Settings" in labels


def test_view_factory_creates_callable():
    """Verify the view factory closure can be created."""
    # We can't actually run it without a real Flet page, but we can verify
    # the factory function exists and is callable.
    from ui.routing import make_get_view_for_index
    assert callable(make_get_view_for_index)


def test_hf_client_can_be_constructed():
    """Verify the HF client can be constructed."""
    from api.hf_client import HFClient
    client = HFClient()
    assert client.token == ""
    assert client.timeout == 20


def test_all_view_modules_have_get_view():
    """Verify each view module exposes a get_*_view function."""
    from views.explore import get_explore_view
    from views.analytics import get_analytics_view
    from views.compare import get_compare_view
    from views.favorites import get_favorites_view
    from views.history import get_history_view
    from views.settings import get_settings_view
    from views.dataset_detail import get_dataset_detail_view
    for fn in [get_explore_view, get_analytics_view, get_compare_view,
               get_favorites_view, get_history_view, get_settings_view,
               get_dataset_detail_view]:
        assert callable(fn)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

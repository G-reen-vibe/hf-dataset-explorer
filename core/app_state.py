"""Centralized page/session state for the HF Dataset Explorer."""
from __future__ import annotations

import types
from typing import Any

import flet as ft


def init_page_state(page: ft.Page) -> None:
    """Initialize the per-page state namespace on `page.hf`."""
    page.hf = types.SimpleNamespace(
        # Settings
        api_token="",
        theme_mode="dark",
        # Caches
        last_search=None,
        last_datasets_page=None,
        # Navigation
        current_view="explore",
        detail_dataset_id=None,
        compare_selections=[],
        # Search state
        search_query="",
        search_author="",
        search_tags=[],
        # For recall from detail views
        back_stack=[],
    )


def get(page: ft.Page, key: str, default: Any = None) -> Any:
    return getattr(page.hf, key, default)


def set(page: ft.Page, key: str, value: Any) -> None:
    setattr(page.hf, key, value)


def push_back(page: ft.Page, view_name: str, **context) -> None:
    """Push the current view onto a back stack before navigating away."""
    stack = getattr(page.hf, "back_stack", []) or []
    stack.append({"view": view_name, "context": context})
    page.hf.back_stack = stack


def pop_back(page: ft.Page):
    stack = getattr(page.hf, "back_stack", []) or []
    if not stack:
        return None
    item = stack.pop()
    page.hf.back_stack = stack
    return item

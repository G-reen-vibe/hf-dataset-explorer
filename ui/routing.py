"""View router: maps nav index to a view builder."""
from __future__ import annotations

import logging
import traceback

import flet as ft

from core import app_state, storage
from views.explore import get_explore_view
from views.analytics import get_analytics_view
from views.compare import get_compare_view
from views.favorites import get_favorites_view
from views.history import get_history_view
from views.settings import get_settings_view
from views.dataset_detail import get_dataset_detail_view

logger = logging.getLogger(__name__)


def make_get_view_for_index(page: ft.Page):
    """Return a closure get_view_for_index(index) bound to the page."""

    def get_view_for_index(index: int):
        try:
            if index == 0:
                return get_explore_view(page)
            if index == 1:
                return get_analytics_view(page)
            if index == 2:
                return get_compare_view(page)
            if index == 3:
                return get_favorites_view(page)
            if index == 4:
                return get_history_view(page)
            if index == 5:
                return get_settings_view(page)
            return ft.Text("Unknown view")
        except Exception as ex:
            logger.error("Error loading view %s: %s", index, ex, exc_info=True)
            return ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR, color="red", size=40),
                    ft.Text(f"Error loading view #{index}:", color="red",
                            weight=ft.FontWeight.BOLD),
                    ft.Text(str(ex), color="red"),
                    ft.Text(traceback.format_exc(), size=10,
                            font_family="Consolas"),
                ],
                scroll=True,
                padding=20,
            )

    return get_view_for_index


def open_dataset_detail(page: ft.Page, dataset_id: str,
                        from_view: str = "explore") -> None:
    """Navigate to the dataset detail view (replaces content_area content)."""
    app_state.push_back(page, from_view)
    app_state.set(page, "detail_dataset_id", dataset_id)
    app_state.set(page, "current_view", "detail")

    def _back():
        item = app_state.pop_back(page)
        if not item:
            # Default back to explore
            page.nav_rail.selected_index = 0
            page.nav_rail.update()
            page.content_area.content = page.mrma_get_view_for_index(0)
            try:
                page.content_area.update()
            except Exception:
                pass
            return
        back_view = item["view"]
        if back_view == "explore":
            idx = 0
        elif back_view == "analytics":
            idx = 1
        elif back_view == "compare":
            idx = 2
        elif back_view == "favorites":
            idx = 3
        elif back_view == "history":
            idx = 4
        else:
            idx = 0
        page.nav_rail.selected_index = idx
        page.nav_rail.update()
        page.content_area.content = page.mrma_get_view_for_index(idx)
        try:
            page.content_area.update()
        except Exception:
            pass

    page._detail_back = _back
    page.content_area.content = get_dataset_detail_view(page, dataset_id, on_back=_back)
    try:
        page.content_area.update()
    except Exception:
        pass


def apply_theme_and_refresh(page: ft.Page) -> None:
    """Re-apply theme and refresh the current view."""
    from ui.theme import apply_theme
    apply_theme(page)
    if getattr(page, "nav_rail", None) and getattr(page, "content_area", None):
        idx = page.nav_rail.selected_index
        if getattr(page, "current_view", "explore") == "detail":
            ds_id = app_state.get(page, "detail_dataset_id")
            if ds_id:
                back = getattr(page, "_detail_back", lambda: None)
                page.content_area.content = get_dataset_detail_view(page, ds_id, on_back=back)
        else:
            page.content_area.content = page.mrma_get_view_for_index(idx)
        try:
            page.content_area.update()
        except Exception:
            pass
        # Rebuild the entire shell so theme colors update everywhere
        # We do this by re-rendering the dashboard, but preserving the index.
        from ui.navigation import show_main_dashboard
        # Re-define get_view_for_index closure to keep it bound.
        gv = page.mrma_get_view_for_index
        show_main_dashboard(page, get_view_for_index=gv)

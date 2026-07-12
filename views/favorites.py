"""Favorites view: list saved datasets."""
from __future__ import annotations

import logging
from typing import Any, Dict

import flet as ft

from core import storage
from ui.theme import effective_theme_mode
from utils.ui_helpers import (
    empty_view,
    muted_text_color,
    page_container,
    section_header,
    show_success,
    text_color,
)

logger = logging.getLogger(__name__)


def get_favorites_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)
    state = {"results": storage.list_favorites()}

    content_col = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
    header = section_header(
        "Favorites",
        theme_mode=theme_mode,
        subtitle="Your saved datasets",
        action=ft.TextButton(
            "Clear all",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=lambda e: _clear_all(page, state, content_col, theme_mode),
        ) if state["results"] else None,
    )

    main_col = ft.Column(
        [header, content_col],
        spacing=12,
        expand=True,
    )

    def _render():
        try:
            content_col.controls.clear()
            if not state["results"]:
                content_col.controls.append(
                    empty_view(
                        "No favorites yet. Click the heart icon on any dataset to save it here.",
                        icon=ft.Icons.FAVORITE_BORDER, theme_mode=theme_mode,
                    )
                )
            else:
                from utils.ui_helpers import dataset_card
                for ds in state["results"]:
                    content_col.controls.append(
                        dataset_card(
                            ds,
                            on_open=lambda d=ds: _open(page, d),
                            on_favorite=lambda d=ds: _remove(page, d, state, content_col, theme_mode),
                            is_favorite=True,
                            theme_mode=theme_mode,
                        )
                    )
            content_col.update()
        except Exception as ex:
            logger.error("Favorites render error: %s", ex, exc_info=True)

    _render()
    return page_container(main_col, theme_mode=theme_mode)


def _open(page: ft.Page, dataset: Dict[str, Any]) -> None:
    storage.add_history(dataset)
    from ui.routing import open_dataset_detail
    open_dataset_detail(page, dataset.get("id"), from_view="favorites")


def _remove(page: ft.Page, dataset: Dict[str, Any], state: Dict[str, Any],
            content_col: ft.Column, theme_mode: str) -> None:
    storage.remove_favorite(dataset.get("id", ""))
    state["results"] = [d for d in state["results"] if d.get("id") != dataset.get("id")]
    show_success(page, f"Removed '{dataset.get('id')}' from favorites")
    # Re-render
    try:
        content_col.controls.clear()
        if not state["results"]:
            content_col.controls.append(
                empty_view(
                    "No favorites yet. Click the heart icon on any dataset to save it here.",
                    icon=ft.Icons.FAVORITE_BORDER, theme_mode=theme_mode,
                )
            )
        else:
            from utils.ui_helpers import dataset_card
            for ds in state["results"]:
                content_col.controls.append(
                    dataset_card(
                        ds,
                        on_open=lambda d=ds: _open(page, d),
                        on_favorite=lambda d=ds: _remove(page, d, state, content_col, theme_mode),
                        is_favorite=True,
                        theme_mode=theme_mode,
                    )
                )
        content_col.update()
    except Exception:
        pass


def _clear_all(page: ft.Page, state: Dict[str, Any], content_col: ft.Column,
               theme_mode: str) -> None:
    for d in list(state["results"]):
        storage.remove_favorite(d.get("id", ""))
    state["results"] = []
    show_success(page, "Cleared all favorites")
    try:
        content_col.controls.clear()
        content_col.controls.append(
            empty_view(
                "No favorites yet. Click the heart icon on any dataset to save it here.",
                icon=ft.Icons.FAVORITE_BORDER, theme_mode=theme_mode,
            )
        )
        content_col.update()
    except Exception:
        pass

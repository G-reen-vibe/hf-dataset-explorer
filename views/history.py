"""History view: list recently viewed datasets."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

import flet as ft

from core import storage
from ui.theme import effective_theme_mode
from utils.formatters import format_relative_date
from utils.ui_helpers import (
    border_color,
    empty_view,
    muted_text_color,
    page_container,
    section_header,
    show_success,
    surface_bg,
    text_color,
)

logger = logging.getLogger(__name__)


def get_history_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)
    state = {"results": storage.list_history()}

    content_col = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
    header = section_header(
        "History",
        theme_mode=theme_mode,
        subtitle="Recently viewed datasets",
        action=ft.TextButton(
            "Clear history",
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
                        "No history yet. Datasets you view will appear here.",
                        icon=ft.Icons.HISTORY, theme_mode=theme_mode,
                    )
                )
            else:
                from utils.ui_helpers import dataset_card
                for ds in state["results"]:
                    viewed_at = ds.get("viewed_at")
                    viewed_str = format_relative_date(
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(viewed_at))
                    ) if viewed_at else ""
                    content_col.controls.append(
                        ft.Column(
                            [
                                dataset_card(
                                    ds,
                                    on_open=lambda d=ds: _open(page, d),
                                    on_favorite=lambda d=ds: _toggle_fav(page, d, state,
                                                                          content_col, theme_mode),
                                    is_favorite=storage.is_favorite(d.get("id", "")),
                                    theme_mode=theme_mode,
                                ),
                                ft.Text(f"  Viewed {viewed_str}", size=10,
                                        color=muted_text_color(theme_mode))
                                if viewed_str else ft.Container(),
                            ],
                            spacing=2, tight=True,
                        )
                    )
            content_col.update()
        except Exception as ex:
            logger.error("History render error: %s", ex, exc_info=True)

    _render()
    return page_container(main_col, theme_mode=theme_mode)


def _open(page: ft.Page, dataset: Dict[str, Any]) -> None:
    storage.add_history(dataset)
    from ui.routing import open_dataset_detail
    open_dataset_detail(page, dataset.get("id"), from_view="history")


def _toggle_fav(page: ft.Page, dataset: Dict[str, Any], state: Dict[str, Any],
                content_col: ft.Column, theme_mode: str) -> None:
    new = storage.toggle_favorite(dataset)
    if new:
        show_success(page, f"Added '{dataset.get('id')}' to favorites")
    else:
        show_success(page, f"Removed '{dataset.get('id')}' from favorites")
    # Re-render
    try:
        content_col.controls.clear()
        from utils.ui_helpers import dataset_card
        for ds in state["results"]:
            viewed_at = ds.get("viewed_at")
            viewed_str = format_relative_date(
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(viewed_at))
            ) if viewed_at else ""
            content_col.controls.append(
                ft.Column(
                    [
                        dataset_card(
                            ds,
                            on_open=lambda d=ds: _open(page, d),
                            on_favorite=lambda d=ds: _toggle_fav(page, d, state,
                                                                  content_col, theme_mode),
                            is_favorite=storage.is_favorite(d.get("id", "")),
                            theme_mode=theme_mode,
                        ),
                        ft.Text(f"  Viewed {viewed_str}", size=10,
                                color=muted_text_color(theme_mode))
                        if viewed_str else ft.Container(),
                    ],
                    spacing=2, tight=True,
                )
            )
        content_col.update()
    except Exception:
        pass


def _clear_all(page: ft.Page, state: Dict[str, Any], content_col: ft.Column,
               theme_mode: str) -> None:
    storage.clear_history()
    state["results"] = []
    show_success(page, "History cleared")
    try:
        content_col.controls.clear()
        content_col.controls.append(
            empty_view(
                "No history yet. Datasets you view will appear here.",
                icon=ft.Icons.HISTORY, theme_mode=theme_mode,
            )
        )
        content_col.update()
    except Exception:
        pass

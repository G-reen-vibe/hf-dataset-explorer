"""Main dashboard shell with horizontal navigation bar."""
from __future__ import annotations

import types
from typing import Callable

import flet as ft

from utils.ui_helpers import (
    PRIMARY,
    PRIMARY_DARK,
    SURFACE_DARK,
    SURFACE_LIGHT,
    page_bg,
    text_color,
    muted_text_color,
)


_DESTINATIONS = [
    (ft.Icons.EXPLORE, "Explore"),
    (ft.Icons.INSIGHTS, "Analytics"),
    (ft.Icons.COMPARE_ARROWS, "Compare"),
    (ft.Icons.FAVORITE, "Favorites"),
    (ft.Icons.HISTORY, "History"),
    (ft.Icons.SETTINGS, "Settings"),
]


def show_main_dashboard(page: ft.Page, *, get_view_for_index: Callable) -> None:
    """Render the main shell: top nav bar + content area."""
    from ui.theme import effective_theme_mode
    theme_mode = effective_theme_mode(page)

    content_area = ft.Container(expand=True, padding=0)
    page.content_area = content_area

    # Logo / title row at the very top
    title_row = ft.Container(
        padding=ft.Padding(left=20, right=20, top=10, bottom=10),
        bgcolor=page_bg(theme_mode),
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=32, height=32,
                            border_radius=8,
                            bgcolor=PRIMARY,
                            content=ft.Icon(ft.Icons.HUB, color="#1F2937", size=20),
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            [
                                ft.Text("HF Dataset Explorer", size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=text_color(theme_mode)),
                                ft.Text("Browse · Analyze · Compare", size=10,
                                        color=muted_text_color(theme_mode)),
                            ],
                            spacing=0, tight=True,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(expand=True),
                _build_search_quick(page),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    nav_row = ft.Row(spacing=0)

    def _item_content(icon, label, is_selected):
        return ft.Column(
            [
                ft.Icon(
                    icon, size=20,
                    color=PRIMARY if is_selected else muted_text_color(theme_mode),
                ),
                ft.Text(
                    label, size=11,
                    weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                    color=PRIMARY if is_selected else muted_text_color(theme_mode),
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            tight=True,
        )

    def _build_item(i, icon, label, is_selected):
        return ft.Container(
            content=_item_content(icon, label, is_selected),
            padding=ft.Padding(left=16, right=16, top=8, bottom=8),
            expand=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda e, idx=i: _select(idx),
            border_radius=8,
            ink=True,
            tooltip=f"{label} (tab {i+1} of {len(_DESTINATIONS)})",
            bgcolor=ft.Colors.with_opacity(0.08, PRIMARY) if is_selected else None,
            border=ft.Border(bottom=ft.BorderSide(2, PRIMARY) if is_selected
                else ft.BorderSide(0, ft.Colors.TRANSPARENT),),
        )

    def _rebuild_nav():
        nav_row.controls.clear()
        for i, (icon, label) in enumerate(_DESTINATIONS):
            is_sel = i == nav_state.selected_index
            nav_row.controls.append(_build_item(i, icon, label, is_sel))

    def _select(idx):
        nav_state.selected_index = idx
        _rebuild_nav()
        content_area.content = get_view_for_index(idx)
        try:
            nav_row.update()
            content_area.update()
        except Exception:
            pass

    def _do_update():
        _rebuild_nav()
        try:
            nav_row.update()
        except Exception:
            pass

    nav_state = types.SimpleNamespace(
        selected_index=0,
        destinations=_DESTINATIONS,
        update=_do_update,
        select=_select,
    )
    page.nav_rail = nav_state

    _rebuild_nav()
    content_area.content = get_view_for_index(0)

    nav_container = ft.Container(
        padding=ft.Padding(left=20, right=20, top=6, bottom=6),
        bgcolor=page_bg(theme_mode),
        border=ft.Border(bottom=ft.BorderSide(1, SURFACE_DARK if theme_mode == "dark" else SURFACE_LIGHT)),
        content=nav_row,
    )

    dashboard = ft.Column(
        [
            title_row,
            nav_container,
            ft.Divider(height=1, thickness=0, color=ft.Colors.TRANSPARENT),
            content_area,
        ],
        expand=True,
        spacing=0)

    page.root = ft.Container(expand=True, bgcolor=page_bg(theme_mode), content=dashboard)
    page.update()


def _build_search_quick(page: ft.Page) -> ft.Control:
    """A small quick-search field in the title bar that jumps to Explore."""
    from ui.theme import effective_theme_mode
    theme_mode = effective_theme_mode(page)

    field = ft.TextField(
        hint_text="Quick search datasets…",
        hint_style=ft.TextStyle(color=muted_text_color(theme_mode)),
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        width=300,
        text_size=13,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=PRIMARY,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE)
        if theme_mode == "dark" else ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
        border_radius=8,
        on_submit=lambda e: _quick_search(page, e.control.value),
    )
    page.quick_search_field = field
    return field


def _quick_search(page: ft.Page, query: str) -> None:
    """Trigger a search from the title bar."""
    q = (query or "").strip()
    if not q:
        return
    from core import app_state
    app_state.set(page, "search_query", q)
    # Switch to Explore tab and run the search
    page.nav_rail.selected_index = 0
    page.nav_rail.update()
    page.content_area.content = page.mrma_get_view_for_index(0)
    try:
        page.content_area.update()
    except Exception:
        pass

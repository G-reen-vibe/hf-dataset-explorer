"""Settings view: API token, theme, history limits, cache control."""
from __future__ import annotations

import logging

import flet as ft

from api.hf_client import clear_cache
from core import storage
from ui.theme import effective_theme_mode
from utils.ui_helpers import (
    INFO,
    PRIMARY,
    SUCCESS,
    WARNING,
    border_color,
    muted_text_color,
    page_container,
    primary_button,
    secondary_button,
    section_header,
    show_success,
    show_error,
    surface_bg,
    text_color,
)

logger = logging.getLogger(__name__)


def get_settings_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)
    settings = storage.get_settings()

    # ----- Controls -------------------------------------------------------
    token_field = ft.TextField(
        label="HuggingFace API Token (optional)",
        value=settings.get("api_token", ""),
        password=True,
        can_reveal_password=True,
        hint_text="hf_xxx (paste your token here)",
        border_color=border_color(theme_mode),
        focused_border_color=PRIMARY,
        border_radius=8,
        text_size=13,
        dense=True,
        expand=True,
    )

    theme_dropdown = ft.Dropdown(
        label="Theme",
        value=settings.get("theme_mode", "dark"),
        options=[
            ft.dropdown.Option("dark", "Dark"),
            ft.dropdown.Option("light", "Light"),
            ft.dropdown.Option("system", "System"),
        ],
        dense=True,
        border_color=border_color(theme_mode),
        border_radius=8,
        text_size=13,
        width=200,
    )

    history_limit_field = ft.TextField(
        label="History limit",
        value=str(settings.get("history_limit", 50)),
        border_color=border_color(theme_mode),
        focused_border_color=PRIMARY,
        border_radius=8,
        text_size=13,
        dense=True,
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # ----- Sections -------------------------------------------------------
    api_section = ft.Container(
        padding=16,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.KEY, color=WARNING, size=22),
                        ft.Text("API Token", size=16, weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode)),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Most public datasets can be browsed without a token. "
                    "Add one if you want to access gated datasets or your own private datasets. "
                    "Your token is stored locally and never sent anywhere except huggingface.co.",
                    size=12, color=muted_text_color(theme_mode),
                ),
                token_field,
                ft.Row(
                    [
                        primary_button("Save token",
                                       lambda e: _save_token(page, token_field.value)),
                        secondary_button("Get a token",
                                         lambda e: page.launch_url(
                                             "https://huggingface.co/settings/tokens"),
                                         icon=ft.Icons.OPEN_IN_NEW,
                                         theme_mode=theme_mode),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        ),
    )

    appearance_section = ft.Container(
        padding=16,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PALETTE, color=INFO, size=22),
                        ft.Text("Appearance", size=16, weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode)),
                    ],
                    spacing=8,
                ),
                ft.Text("Choose how the application looks.",
                        size=12, color=muted_text_color(theme_mode)),
                ft.Row([theme_dropdown], spacing=8),
                primary_button("Apply",
                               lambda e: _apply_theme(page, theme_dropdown.value)),
            ],
            spacing=10,
        ),
    )

    data_section = ft.Container(
        padding=16,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.STORAGE, color=SUCCESS, size=22),
                        ft.Text("Data & Cache", size=16, weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode)),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Adjust how many recently-viewed datasets are kept in history.",
                    size=12, color=muted_text_color(theme_mode),
                ),
                ft.Row([history_limit_field], spacing=8),
                primary_button("Save",
                               lambda e: _save_history_limit(page,
                                                             history_limit_field.value)),
                ft.Divider(),
                ft.Text(
                    "Clear cached API responses. This will force re-fetching from the Hub on the next request.",
                    size=12, color=muted_text_color(theme_mode),
                ),
                secondary_button("Clear cache",
                                 lambda e: _clear_cache(page),
                                 icon=ft.Icons.CLEANING_SERVICES,
                                 theme_mode=theme_mode),
                ft.Divider(),
                ft.Text(
                    "Remove all favorites and history from local storage.",
                    size=12, color=muted_text_color(theme_mode),
                ),
                secondary_button("Reset all data",
                                 lambda e: _reset_data(page),
                                 icon=ft.Icons.DELETE_FOREVER,
                                 theme_mode=theme_mode),
            ],
            spacing=10,
        ),
    )

    about_section = ft.Container(
        padding=16,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=PRIMARY, size=22),
                        ft.Text("About", size=16, weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode)),
                    ],
                    spacing=8,
                ),
                ft.Text("HF Dataset Explorer", size=14, weight=ft.FontWeight.W_600,
                        color=text_color(theme_mode)),
                ft.Text("Version 1.0.0", size=11, color=muted_text_color(theme_mode)),
                ft.Text(
                    "A desktop application for browsing, analyzing, and comparing datasets on the HuggingFace Hub. "
                    "Built with Flet and Python.",
                    size=12, color=muted_text_color(theme_mode),
                ),
                ft.Row(
                    [
                        secondary_button("HuggingFace Hub",
                                         lambda e: page.launch_url("https://huggingface.co/datasets"),
                                         icon=ft.Icons.OPEN_IN_NEW,
                                         theme_mode=theme_mode),
                        secondary_button("Flet",
                                         lambda e: page.launch_url("https://flet.dev"),
                                         icon=ft.Icons.OPEN_IN_NEW,
                                         theme_mode=theme_mode),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        ),
    )

    main_col = ft.Column(
        [
            section_header("Settings", theme_mode=theme_mode),
            api_section,
            appearance_section,
            data_section,
            about_section,
        ],
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
        expand=True)

    return page_container(main_col, theme_mode=theme_mode)


def _save_token(page: ft.Page, token: str) -> None:
    storage.set_setting("api_token", (token or "").strip())
    # Force client re-init
    from api.hf_client import get_client
    get_client((token or "").strip())
    show_success(page, "API token saved.")


def _apply_theme(page: ft.Page, theme_mode: str) -> None:
    storage.set_setting("theme_mode", theme_mode)
    from ui.routing import apply_theme_and_refresh
    apply_theme_and_refresh(page)
    show_success(page, f"Theme set to {theme_mode}.")


def _save_history_limit(page: ft.Page, value: str) -> None:
    try:
        limit = int(value)
        if limit < 0 or limit > 1000:
            raise ValueError("Out of range")
        storage.set_setting("history_limit", limit)
        show_success(page, f"History limit set to {limit}.")
    except ValueError:
        show_error(page, "Please enter a valid number between 0 and 1000.")


def _clear_cache(page: ft.Page) -> None:
    clear_cache()
    show_success(page, "Cache cleared.")


def _reset_data(page: ft.Page) -> None:
    # Clear favorites
    for d in storage.list_favorites():
        storage.remove_favorite(d.get("id", ""))
    storage.clear_history()
    show_success(page, "All favorites and history cleared.")

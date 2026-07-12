"""Application theme configuration."""
from __future__ import annotations

import flet as ft

from utils.ui_helpers import (
    ACCENT,
    ACCENT_LIGHT,
    BG_DARK,
    BG_LIGHT,
    BORDER_DARK,
    BORDER_LIGHT,
    PRIMARY,
    PRIMARY_DARK,
    SURFACE_DARK,
    SURFACE_LIGHT,
)


def light_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=PRIMARY_DARK,
            on_primary="#1F2937",
            primary_container="#FEF3C7",
            on_primary_container="#78350F",
            secondary=ACCENT,
            on_secondary="#FFFFFF",
            secondary_container="#F3E8FF",
            on_secondary_container="#4C1D95",
            surface=BG_LIGHT,
            on_surface="#1F2937",
            on_surface_variant="#4B5563",
            surface_container_high=SURFACE_LIGHT,
            surface_container_highest="#EDF0F4",
            surface_container_low="#FCFCFD",
            surface_container_lowest="#FFFFFF",
            outline=BORDER_LIGHT,
            outline_variant="#E5E7EB",
            error="#DC2626",
            on_error="#FFFFFF",
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(color="#1F2937"),
            body_medium=ft.TextStyle(color="#1F2937"),
            body_small=ft.TextStyle(color="#4B5563"),
            title_large=ft.TextStyle(color="#111827", weight=ft.FontWeight.BOLD),
            title_medium=ft.TextStyle(color="#1F2937", weight=ft.FontWeight.W_600),
            title_small=ft.TextStyle(color="#374151", weight=ft.FontWeight.W_600),
            label_large=ft.TextStyle(color="#1F2937"),
            label_medium=ft.TextStyle(color="#4B5563"),
            label_small=ft.TextStyle(color="#6B7280"),
            headline_medium=ft.TextStyle(color="#111827", weight=ft.FontWeight.BOLD),
        ),
    )


def dark_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=PRIMARY,
            on_primary="#0B0F19",
            primary_container="#3D3A0F",
            on_primary_container="#FEF3C7",
            secondary=ACCENT_LIGHT,
            on_secondary="#FFFFFF",
            secondary_container="#3B0764",
            on_secondary_container="#F3E8FF",
            surface=BG_DARK,
            on_surface="#F3F4F6",
            on_surface_variant="#9CA3AF",
            surface_container=SURFACE_DARK,
            surface_container_high="#1F2530",
            surface_container_highest="#262C36",
            surface_container_low="#11161F",
            surface_container_lowest="#070A11",
            outline=BORDER_DARK,
            outline_variant="#1F2530",
            error="#F87171",
            on_error="#1F0606",
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(color="#F3F4F6"),
            body_medium=ft.TextStyle(color="#F3F4F6"),
            body_small=ft.TextStyle(color="#9CA3AF"),
            title_large=ft.TextStyle(color="#FFFFFF", weight=ft.FontWeight.BOLD),
            title_medium=ft.TextStyle(color="#F3F4F6", weight=ft.FontWeight.W_600),
            title_small=ft.TextStyle(color="#E5E7EB", weight=ft.FontWeight.W_600),
            label_large=ft.TextStyle(color="#F3F4F6"),
            label_medium=ft.TextStyle(color="#9CA3AF"),
            label_small=ft.TextStyle(color="#6B7280"),
            headline_medium=ft.TextStyle(color="#FFFFFF", weight=ft.FontWeight.BOLD),
        ),
    )


def apply_theme(page: ft.Page) -> None:
    from core import storage
    theme_mode = storage.get_setting("theme_mode", "dark")
    page.theme_mode = {
        "dark": ft.ThemeMode.DARK,
        "light": ft.ThemeMode.LIGHT,
        "system": ft.ThemeMode.SYSTEM,
    }.get(theme_mode, ft.ThemeMode.DARK)
    page.theme = light_theme()
    page.dark_theme = dark_theme()
    try:
        page.update()
    except Exception:
        pass


def current_theme_mode(page: ft.Page) -> str:
    from core import storage
    return storage.get_setting("theme_mode", "dark")


def effective_theme_mode(page: ft.Page) -> str:
    """Return 'dark' or 'light', resolving 'system' to the actual current mode."""
    mode = current_theme_mode(page)
    if mode == "system":
        # Flet exposes the resolved theme via page.theme_mode after apply_theme
        return "dark" if page.theme_mode == ft.ThemeMode.DARK else "light"
    return mode

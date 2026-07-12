"""Reusable Flet UI helpers: cards, stat blocks, snackbars, loading spinners."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import flet as ft

from utils.formatters import (
    format_compact,
    format_int,
    format_relative_date,
    pretty_tag,
    truncate,
)
from api.hf_client import parse_tags


# --------------------------------------------------------------------------- #
# Theme colors
# --------------------------------------------------------------------------- #

PRIMARY = "#FFD21E"            # HF yellow
PRIMARY_DARK = "#FFB400"
ACCENT = "#7E22CE"             # HF purple
ACCENT_LIGHT = "#A855F7"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
INFO = "#3B82F6"

BG_LIGHT = "#FFFFFF"
BG_DARK = "#0B0F19"
SURFACE_DARK = "#161B26"
SURFACE_LIGHT = "#F8F9FB"
BORDER_LIGHT = "#E5E7EB"
BORDER_DARK = "#262C36"


def surface_bg(theme_mode: str) -> str:
    return SURFACE_DARK if theme_mode == "dark" else SURFACE_LIGHT


def border_color(theme_mode: str) -> str:
    return BORDER_DARK if theme_mode == "dark" else BORDER_LIGHT


def page_bg(theme_mode: str) -> str:
    return BG_DARK if theme_mode == "dark" else BG_LIGHT


def text_color(theme_mode: str) -> str:
    return "#F3F4F6" if theme_mode == "dark" else "#1F2937"


def muted_text_color(theme_mode: str) -> str:
    return "#9CA3AF" if theme_mode == "dark" else "#6B7280"


# --------------------------------------------------------------------------- #
# Snackbars
# --------------------------------------------------------------------------- #

def show_snack(page: ft.Page, message: str, color: str = INFO,
               duration: int = 3000) -> None:
    """Show a snackbar at the bottom of the page."""
    snack = ft.SnackBar(
        content=ft.Row(
            [
                ft.Icon(_icon_for_color(color), color=color, size=18),
                ft.Text(message, color="white", expand=True),
            ],
            spacing=8,
        ),
        bgcolor="#1F2937" if color == INFO else color,
        duration=duration,
    )
    page.overlay.append(snack)
    snack.open = True
    try:
        page.update()
    except Exception:
        pass


def show_error(page: ft.Page, message: str) -> None:
    show_snack(page, message, color=DANGER, duration=4000)


def show_success(page: ft.Page, message: str) -> None:
    show_snack(page, message, color=SUCCESS)


def _icon_for_color(color: str) -> str:
    if color == DANGER:
        return ft.Icons.ERROR
    if color == SUCCESS:
        return ft.Icons.CHECK_CIRCLE
    if color == WARNING:
        return ft.Icons.WARNING
    return ft.Icons.INFO


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def loading_view(message: str = "Loading…", theme_mode: str = "dark") -> ft.Control:
    return ft.Column(
        [
            ft.ProgressRing(width=40, height=40, stroke_width=3),
            ft.Text(message, color=muted_text_color(theme_mode), size=14),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def empty_view(message: str, icon: str = ft.Icons.INBOX_OUTLINED,
               theme_mode: str = "dark") -> ft.Control:
    return ft.Column(
        [
            ft.Icon(icon, size=56, color=muted_text_color(theme_mode)),
            ft.Text(message, color=muted_text_color(theme_mode), size=15, text_align=ft.TextAlign.CENTER),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def error_view(message: str, theme_mode: str = "dark") -> ft.Control:
    return ft.Column(
        [
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=DANGER),
            ft.Text("Something went wrong", size=18, weight=ft.FontWeight.BOLD,
                    color=text_color(theme_mode)),
            ft.Text(message, color=muted_text_color(theme_mode), text_align=ft.TextAlign.CENTER),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        scroll=True,
    )


# --------------------------------------------------------------------------- #
# Cards & chips
# --------------------------------------------------------------------------- #

def stat_chip(icon: str, label: str, value: str, color: str = INFO,
              theme_mode: str = "dark") -> ft.Control:
    """Small horizontal stat block: icon + label + value."""
    return ft.Container(
        padding=ft.Padding(left=10, right=10, top=8, bottom=8),
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=8,
        bgcolor=surface_bg(theme_mode),
        content=ft.Row(
            [
                ft.Icon(icon, color=color, size=18),
                ft.Column(
                    [
                        ft.Text(label, size=10, color=muted_text_color(theme_mode),
                                weight=ft.FontWeight.W_500),
                        ft.Text(value, size=14, weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode)),
                    ],
                    spacing=2,
                    tight=True,
                ),
            ],
            spacing=8,
            tight=True,
        ),
    )


def tag_chip(text: str, color: str = ACCENT, on_click: Optional[Callable] = None,
             theme_mode: str = "dark", small: bool = False) -> ft.Control:
    """A pill-shaped tag chip."""
    text_size = 10 if small else 11
    pad_h = 6 if small else 8
    pad_v = 2 if small else 3
    return ft.Container(
        padding=ft.Padding(left=pad_h, right=pad_h, top=pad_v, bottom=pad_v),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border=ft.Border(top=ft.BorderSide(1, ft.Colors.with_opacity(0.3, color)), bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.3, color)), left=ft.BorderSide(1, ft.Colors.with_opacity(0.3, color)), right=ft.BorderSide(1, ft.Colors.with_opacity(0.3, color))),
        content=ft.Text(
            text,
            size=text_size,
            color=color,
            weight=ft.FontWeight.W_600,
            selectable=True,
        ),
        on_click=on_click,
        tooltip=text,
    )


def tag_row(tags: List[str], theme_mode: str = "dark",
            on_tag_click: Optional[Callable] = None,
            max_tags: int = 8) -> ft.Control:
    """Render a list of HF tags as chips, grouped sensibly."""
    if not tags:
        return ft.Text("—", size=12, color=muted_text_color(theme_mode))
    parsed = parse_tags(tags)
    rows: List[ft.Control] = []
    # Order: task, modality, size, language, license, format, library
    order = ["task", "modality", "size", "language", "license", "format", "library", "region", "arxiv"]
    color_map = {
        "task": ACCENT,
        "modality": INFO,
        "size": WARNING,
        "language": SUCCESS,
        "license": PRIMARY_DARK,
        "format": ACCENT_LIGHT,
        "library": "#6366F1",
        "region": "#EC4899",
        "arxiv": "#64748B",
    }
    chips: List[ft.Control] = []
    for cat in order:
        for t in parsed.get(cat, []):
            chips.append(tag_chip(
                pretty_tag(t),
                color=color_map.get(cat, ACCENT),
                on_click=(lambda e, tag=t: on_tag_click(tag)) if on_tag_click else None,
                theme_mode=theme_mode,
            ))
            if len(chips) >= max_tags:
                break
        if len(chips) >= max_tags:
            break
    if len(chips) < len(tags):
        chips.append(ft.Text(f"+{len(tags) - len(chips)} more",
                              size=10, color=muted_text_color(theme_mode)))
    return ft.Row(chips, wrap=True, spacing=6, run_spacing=4)


def section_header(title: str, theme_mode: str = "dark",
                   subtitle: Optional[str] = None,
                   action: Optional[ft.Control] = None) -> ft.Control:
    """A section title row."""
    children = [
        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=text_color(theme_mode)),
    ]
    if subtitle:
        children.append(ft.Text(subtitle, size=12, color=muted_text_color(theme_mode)))
    return ft.Row(
        [
            ft.Column(children, spacing=2, expand=True),
            action or ft.Container(),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER)


# --------------------------------------------------------------------------- #
# Dataset card (used in explore + favorites lists)
# --------------------------------------------------------------------------- #

def dataset_card(
    dataset: Dict[str, Any],
    *,
    on_open: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_favorite: Optional[Callable[[Dict[str, Any]], None]] = None,
    is_favorite: bool = False,
    theme_mode: str = "dark",
    show_description: bool = True,
) -> ft.Control:
    """A clickable card summarizing a dataset."""
    dataset_id = dataset.get("id", "?")
    author = dataset.get("author", "")
    downloads = dataset.get("downloads", 0)
    likes = dataset.get("likes", 0)
    trending = dataset.get("trendingScore", 0) or 0
    last_mod = dataset.get("lastModified")
    tags = dataset.get("tags", []) or []
    description = dataset.get("description") or ""

    # Click handler
    def _on_click(e):
        if on_open:
            on_open(dataset)

    def _on_fav(e):
        e.stop_propagation = True
        if on_favorite:
            on_favorite(dataset)

    fav_icon = ft.Icons.FAVORITE if is_favorite else ft.Icons.FAVORITE_BORDER
    fav_color = DANGER if is_favorite else muted_text_color(theme_mode)

    header_row = ft.Row(
        [
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.DATASET_OUTLINED, size=16,
                                    color=PRIMARY_DARK),
                            ft.Text(
                                dataset_id,
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode),
                                selectable=True,
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        f"by {author} · updated {format_relative_date(last_mod)}"
                        if author else f"updated {format_relative_date(last_mod)}",
                        size=11,
                        color=muted_text_color(theme_mode),
                    ),
                ],
                spacing=2,
                expand=True,
            ),
            ft.IconButton(
                icon=fav_icon,
                icon_color=fav_color,
                icon_size=18,
                tooltip="Remove from favorites" if is_favorite else "Add to favorites",
                on_click=_on_fav,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    stats_row = ft.Row(
        [
            stat_chip(ft.Icons.DOWNLOAD, "Downloads", format_compact(downloads),
                      color=INFO, theme_mode=theme_mode),
            stat_chip(ft.Icons.THUMB_UP, "Likes", format_compact(likes),
                      color=WARNING, theme_mode=theme_mode),
            stat_chip(ft.Icons.TRENDING_UP, "Trending", format_compact(trending),
                      color=SUCCESS if trending > 0 else muted_text_color(theme_mode),
                      theme_mode=theme_mode),
        ],
        spacing=8,
        wrap=True,
        run_spacing=6,
    )

    children: List[ft.Control] = [header_row, stats_row]

    if show_description and description:
        children.append(
            ft.Text(
                truncate(description, 180),
                size=12,
                color=muted_text_color(theme_mode),
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS,
                selectable=True,
            )
        )

    children.append(tag_row(tags, theme_mode=theme_mode, max_tags=6))

    return ft.Container(
        ink=True,
        on_click=_on_click,
        padding=14,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(children, spacing=10, tight=True),
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )


def stat_tile(label: str, value: str, hint: str = "",
              icon: str = ft.Icons.INSERT_CHART_OUTLINED,
              color: str = INFO, theme_mode: str = "dark") -> ft.Control:
    """A large square-ish stat tile for dashboards."""
    return ft.Container(
        padding=16,
        border=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        border_radius=12,
        bgcolor=surface_bg(theme_mode),
        expand=True,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icon, color=color, size=22),
                        ft.Container(expand=True),
                    ]),
                ft.Container(height=4),
                ft.Text(value, size=22, weight=ft.FontWeight.BOLD,
                        color=text_color(theme_mode)),
                ft.Text(label, size=11, color=muted_text_color(theme_mode)),
            ] + ([ft.Text(hint, size=10, color=muted_text_color(theme_mode))]
                 if hint else []),
            spacing=2,
            tight=True,
        ),
    )


def page_container(content: ft.Control, theme_mode: str = "dark") -> ft.Control:
    """Wrap a view's content in a scrollable padded container."""
    return ft.Container(
        expand=True,
        padding=24,
        content=ft.Column(
            [content],
            scroll=ft.ScrollMode.AUTO,
            expand=True),
    )


def primary_button(text: str, on_click: Callable, *,
                   icon: Optional[str] = None,
                   disabled: bool = False,
                   expand: bool = False) -> ft.Control:
    return ft.ElevatedButton(
        text,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        bgcolor=PRIMARY,
        color="#1F2937",
        style=ft.ButtonStyle(
            padding=ft.Padding(left=18, right=18, top=10, bottom=10),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
        expand=expand,
    )


def secondary_button(text: str, on_click: Callable, *,
                     icon: Optional[str] = None,
                     disabled: bool = False,
                     expand: bool = False,
                     theme_mode: str = "dark") -> ft.Control:
    return ft.OutlinedButton(
        text,
        icon=icon,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            padding=ft.Padding(left=18, right=18, top=10, bottom=10),
            shape=ft.RoundedRectangleBorder(radius=8),
            side=ft.Border(top=ft.BorderSide(1, border_color(theme_mode)), bottom=ft.BorderSide(1, border_color(theme_mode)), left=ft.BorderSide(1, border_color(theme_mode)), right=ft.BorderSide(1, border_color(theme_mode))),
        ),
        expand=expand,
    )

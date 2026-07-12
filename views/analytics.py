"""Analytics view: aggregate insights across popular datasets."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

import flet as ft

from api.hf_client import HFError, categorize_tag, get_client
from core import storage
from ui.theme import effective_theme_mode
from utils.formatters import format_compact, format_int, pretty_tag
from utils.ui_helpers import (
    ACCENT,
    INFO,
    PRIMARY,
    SUCCESS,
    WARNING,
    border_color,
    empty_view,
    error_view,
    loading_view,
    muted_text_color,
    page_container,
    section_header,
    show_error,
    stat_tile,
    surface_bg,
    text_color,
)

logger = logging.getLogger(__name__)


def get_analytics_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)
    state = {"loading": True, "error": None, "data": None}

    content_col = ft.Column(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
    content_col.controls.append(loading_view("Crunching the numbers…", theme_mode))

    header = section_header(
        "Analytics",
        theme_mode=theme_mode,
        subtitle="Aggregate insights across trending datasets on the Hub",
    )

    # Sample size selector
    sample_dd = ft.Dropdown(
        label="Sample size",
        value="100",
        options=[ft.dropdown.Option("50"), ft.dropdown.Option("100"),
                 ft.dropdown.Option("200"), ft.dropdown.Option("500")],
        dense=True, width=160, text_size=12,
        border_color=border_color(theme_mode), border_radius=8,
        on_change=lambda e: _refresh(page, state, content_col,
                                      int(e.control.value), theme_mode),
    )

    main_col = ft.Column(
        [
            ft.Row(
                [header, sample_dd],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content_col,
        ],
        spacing=12,
        expand=True,
    )

    def _initial():
        _refresh(page, state, content_col, 100, theme_mode)

    page.run_thread(_initial)
    return page_container(main_col, theme_mode=theme_mode)


def _refresh(page: ft.Page, state: Dict[str, Any], content_col: ft.Column,
             sample_size: int, theme_mode: str) -> None:
    state["loading"] = True
    try:
        content_col.controls.clear()
        content_col.controls.append(loading_view("Crunching the numbers…", theme_mode))
        content_col.update()
    except Exception:
        pass

    def _run():
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            # Fetch top datasets by downloads, likes, and trending
            top_downloads = client.get_most_downloaded(limit=sample_size)
            top_likes = client.get_most_liked(limit=sample_size)
            trending = client.get_trending(limit=sample_size)

            state["data"] = {
                "top_downloads": top_downloads,
                "top_likes": top_likes,
                "trending": trending,
            }
            state["loading"] = False
            _render(page, state, content_col, theme_mode)
        except HFError as ex:
            state["error"] = str(ex)
            content_col.controls.clear()
            content_col.controls.append(error_view(str(ex), theme_mode))
            try:
                content_col.update()
            except Exception:
                pass
        except Exception as ex:
            logger.error("Analytics error: %s", ex, exc_info=True)
            state["error"] = str(ex)
            content_col.controls.clear()
            content_col.controls.append(error_view(str(ex), theme_mode))
            try:
                content_col.update()
            except Exception:
                pass

    page.run_thread(_run)


def _render(page: ft.Page, state: Dict[str, Any], content_col: ft.Column,
            theme_mode: str) -> None:
    data = state.get("data")
    if not data:
        return
    try:
        content_col.controls.clear()

        # ----- KPI tiles -----------------------------------------------------
        top_downloads = data["top_downloads"]
        top_likes = data["top_likes"]
        trending = data["trending"]

        total_downloads = sum(d.get("downloads", 0) for d in top_downloads)
        total_likes = sum(d.get("likes", 0) for d in top_likes)
        avg_trending = (sum(d.get("trendingScore", 0) or 0 for d in trending)
                        / max(1, len(trending)))
        unique_authors = len({d.get("author", "") for d in top_downloads if d.get("author")})

        content_col.controls.append(
            ft.Row(
                [
                    stat_tile("Total Downloads", format_compact(total_downloads),
                              hint=f"Top {len(top_downloads)} datasets",
                              icon=ft.Icons.DOWNLOAD, color=INFO, theme_mode=theme_mode),
                    stat_tile("Total Likes", format_compact(total_likes),
                              hint=f"Top {len(top_likes)} datasets",
                              icon=ft.Icons.THUMB_UP, color=WARNING, theme_mode=theme_mode),
                    stat_tile("Avg Trending", format_compact(avg_trending),
                              hint=f"Top {len(trending)} trending",
                              icon=ft.Icons.TRENDING_UP, color=SUCCESS, theme_mode=theme_mode),
                    stat_tile("Unique Authors", format_int(unique_authors),
                              hint=f"Across top {len(top_downloads)}",
                              icon=ft.Icons.GROUP, color=ACCENT, theme_mode=theme_mode),
                ],
                spacing=10, wrap=True, run_spacing=10,
            )
        )

        # ----- Top 10 by downloads (bar chart) -------------------------------
        content_col.controls.append(
            _build_bar_chart(
                "Top 10 Datasets by Downloads",
                [(d.get("id", "?"), d.get("downloads", 0)) for d in top_downloads[:10]],
                color=INFO, theme_mode=theme_mode,
            )
        )

        # ----- Top 10 by likes (bar chart) ----------------------------------
        content_col.controls.append(
            _build_bar_chart(
                "Top 10 Datasets by Likes",
                [(d.get("id", "?"), d.get("likes", 0)) for d in top_likes[:10]],
                color=WARNING, theme_mode=theme_mode,
            )
        )

        # ----- Top 10 trending (bar chart) ----------------------------------
        content_col.controls.append(
            _build_bar_chart(
                "Top 10 Trending Datasets",
                [(d.get("id", "?"), d.get("trendingScore", 0) or 0) for d in trending[:10]],
                color=SUCCESS, theme_mode=theme_mode,
            )
        )

        # ----- Tag distribution (combined across all three lists) -----------
        all_datasets = top_downloads + top_likes + trending
        content_col.controls.append(
            _build_tag_distribution(all_datasets, theme_mode)
        )

        # ----- Top authors --------------------------------------------------
        content_col.controls.append(
            _build_top_authors(all_datasets, theme_mode)
        )

        try:
            content_col.update()
        except Exception:
            pass

    except Exception as ex:
        logger.error("Analytics render error: %s", ex, exc_info=True)


def _build_bar_chart(title: str, items: List[tuple], color: str,
                     theme_mode: str) -> ft.Control:
    """Build a horizontal bar chart of (label, value) pairs."""
    if not items:
        return ft.Column([
            section_header(title, theme_mode=theme_mode),
            empty_view("No data available", theme_mode=theme_mode),
        ])

    max_val = max(v for _, v in items) or 1
    rows: List[ft.Control] = []

    for label, value in items:
        # Shorten label
        short_label = label if len(label) <= 30 else "…" + label[-28:]
        pct = (value / max_val) * 100 if max_val else 0
        bar_color = color
        rows.append(
            ft.Row(
                [
                    ft.Container(
                        width=180,
                        content=ft.Text(short_label, size=11,
                                        color=text_color(theme_mode),
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                        selectable=True, tooltip=label),
                    ),
                    ft.Container(
                        width=pct * 6,  # scale to ~600px max
                        height=18,
                        bgcolor=bar_color,
                        border_radius=4,
                        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
                    ),
                    ft.Text(format_compact(value), size=11,
                            color=muted_text_color(theme_mode),
                            weight=ft.FontWeight.W_500),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    return ft.Container(
        padding=ft.padding.all(14),
        border=ft.border.all(1, border_color(theme_mode)),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                section_header(title, theme_mode=theme_mode),
                ft.Column(rows, spacing=8, tight=True),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def _build_tag_distribution(datasets: List[Dict[str, Any]],
                            theme_mode: str) -> ft.Control:
    """Build a section showing tag category distributions."""
    # Combine all tags
    cat_counter: Counter = Counter()
    detail_counter: Dict[str, Counter] = {}
    for ds in datasets:
        for tag in ds.get("tags", []) or []:
            cat = categorize_tag(tag)
            if not cat:
                continue
            cat_counter[cat] += 1
            detail_counter.setdefault(cat, Counter())[tag] += 1

    if not cat_counter:
        return ft.Column([
            section_header("Tag Distribution", theme_mode=theme_mode),
            empty_view("No tags available", theme_mode=theme_mode),
        ])

    sections: List[ft.Control] = [section_header("Tag Distribution",
                                                  theme_mode=theme_mode,
                                                  subtitle=f"Across {len(datasets)} datasets")]

    # Order categories
    order = ["task", "modality", "size", "language", "license", "format"]
    for cat in order:
        if cat not in detail_counter:
            continue
        counter = detail_counter[cat]
        total = sum(counter.values()) or 1
        top_tags = counter.most_common(8)

        chips: List[ft.Control] = []
        for tag, count in top_tags:
            pct = (count / total) * 100
            chips.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border=ft.border.all(1, border_color(theme_mode)),
                    border_radius=8,
                    bgcolor=surface_bg(theme_mode),
                    content=ft.Row(
                        [
                            ft.Text(pretty_tag(tag), size=11,
                                    color=text_color(theme_mode),
                                    weight=ft.FontWeight.W_500),
                            ft.Text(f"{count} ({pct:.0f}%)", size=10,
                                    color=muted_text_color(theme_mode)),
                        ],
                        spacing=6,
                    ),
                )
            )

        sections.append(
            ft.Column(
                [
                    ft.Text(cat.upper(), size=10, weight=ft.FontWeight.BOLD,
                            color=muted_text_color(theme_mode)),
                    ft.Wrap(chips, spacing=6, run_spacing=4),
                ],
                spacing=6, tight=True,
            )
        )

    return ft.Container(
        padding=ft.padding.all(14),
        border=ft.border.all(1, border_color(theme_mode)),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(sections, spacing=12),
    )


def _build_top_authors(datasets: List[Dict[str, Any]],
                       theme_mode: str) -> ft.Control:
    """Build a chart of top authors by dataset count + total downloads."""
    author_counter: Counter = Counter()
    author_downloads: Dict[str, int] = {}
    for ds in datasets:
        author = ds.get("author", "")
        if not author:
            continue
        author_counter[author] += 1
        author_downloads[author] = author_downloads.get(author, 0) + ds.get("downloads", 0)

    if not author_counter:
        return ft.Column([
            section_header("Top Authors", theme_mode=theme_mode),
            empty_view("No author data", theme_mode=theme_mode),
        ])

    top = author_counter.most_common(10)
    max_count = top[0][1] if top else 1

    rows: List[ft.Control] = []
    for author, count in top:
        pct = (count / max_count) * 100
        downloads = author_downloads.get(author, 0)
        rows.append(
            ft.Row(
                [
                    ft.Container(
                        width=160,
                        content=ft.Text(author, size=11,
                                        color=text_color(theme_mode),
                                        selectable=True, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                    ),
                    ft.Container(
                        width=pct * 5, height=18,
                        bgcolor=ACCENT, border_radius=4,
                    ),
                    ft.Text(f"{count} datasets · {format_compact(downloads)} downloads",
                            size=10, color=muted_text_color(theme_mode)),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    return ft.Container(
        padding=ft.padding.all(14),
        border=ft.border.all(1, border_color(theme_mode)),
        border_radius=10,
        bgcolor=surface_bg(theme_mode),
        content=ft.Column(
            [
                section_header("Top Authors / Organizations",
                               theme_mode=theme_mode,
                               subtitle="By dataset count among sampled popular datasets"),
                ft.Column(rows, spacing=8, tight=True),
            ],
            spacing=10,
        ),
    )

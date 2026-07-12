"""Compare view: side-by-side comparison of up to 4 datasets."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import flet as ft

from api.hf_client import HFError, get_client
from core import storage
from ui.theme import effective_theme_mode
from utils.formatters import (
    format_bytes,
    format_compact,
    format_date,
    format_int,
    get_dataset_stats,
    pretty_tag,
)
from api.hf_client import parse_tags
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
    primary_button,
    secondary_button,
    section_header,
    show_error,
    show_success,
    surface_bg,
    text_color,
)

logger = logging.getLogger(__name__)


_MAX_COMPARE = 4


def get_compare_view(page: ft.Page) -> ft.Control:
    theme_mode = effective_theme_mode(page)
    state = {
        "selections": storage.list_favorites()[:_MAX_COMPARE],  # pre-load favorites
        "datasets": {},  # id -> full dataset dict
        "loading": False,
        "error": None,
    }
    # Trim selections to MAX
    state["selections"] = state["selections"][:_MAX_COMPARE]

    search_field = ft.TextField(
        hint_text="Add a dataset by ID (e.g. 'HuggingFaceH4/no_robots')…",
        hint_style=ft.TextStyle(color=muted_text_color(theme_mode)),
        prefix_icon=ft.Icons.ADD,
        border_color=ft.Colors.with_opacity(0.2, text_color(theme_mode)),
        focused_border_color=PRIMARY,
        border_radius=8, text_size=13, dense=True, expand=True,
        on_submit=lambda e: _add_dataset(page, state, e.control.value,
                                         content_col, chips_row, theme_mode),
    )

    add_btn = ft.ElevatedButton(
        "Add", icon=ft.Icons.ADD, on_click=lambda e: _add_dataset(page, state,
                                                                   search_field.value,
                                                                   content_col,
                                                                   chips_row, theme_mode),
        bgcolor=PRIMARY, color="#1F2937",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
    )

    clear_btn = secondary_button(
        "Clear all", lambda e: _clear_all(state, content_col, chips_row, theme_mode),
        icon=ft.Icons.CLEAR, theme_mode=theme_mode,
    )

    chips_row = ft.Row(spacing=6, wrap=True)
    content_col = ft.Column(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)

    header = section_header(
        "Compare Datasets",
        theme_mode=theme_mode,
        subtitle=f"Add up to {_MAX_COMPARE} datasets for side-by-side comparison",
    )

    main_col = ft.Column(
        [
            header,
            ft.Row([search_field, add_btn, clear_btn],
                   spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   wrap=True),
            chips_row,
            content_col,
        ],
        spacing=12,
        expand=True,
    )

    # Initial render
    _refresh_all(page, state, content_col, chips_row, theme_mode)

    return page_container(main_col, theme_mode=theme_mode)


# --------------------------------------------------------------------------- #
# Selection management
# --------------------------------------------------------------------------- #

def _add_dataset(page: ft.Page, state: Dict[str, Any], dataset_id: str,
                 content_col: ft.Column, chips_row: ft.Row,
                 theme_mode: str) -> None:
    dataset_id = (dataset_id or "").strip()
    if not dataset_id:
        return
    # Check if already added
    for s in state["selections"]:
        if s.get("id") == dataset_id:
            show_error(page, f"'{dataset_id}' is already in the comparison.")
            return
    if len(state["selections"]) >= _MAX_COMPARE:
        show_error(page, f"Maximum {_MAX_COMPARE} datasets can be compared at once.")
        return

    # Add a slim placeholder entry
    state["selections"].append({"id": dataset_id, "author": "", "downloads": 0, "likes": 0})

    def _run():
        try:
            token = storage.get_setting("api_token", "")
            client = get_client(token)
            dataset = client.get_dataset(dataset_id)
            # Replace the placeholder with the slim summary
            state["datasets"][dataset_id] = dataset
            # Update the slim entry
            for i, s in enumerate(state["selections"]):
                if s.get("id") == dataset_id:
                    state["selections"][i] = {
                        "id": dataset.get("id"),
                        "author": dataset.get("author"),
                        "downloads": dataset.get("downloads", 0),
                        "likes": dataset.get("likes", 0),
                        "tags": dataset.get("tags", []),
                    }
                    break
            _refresh_all(page, state, content_col, chips_row, theme_mode)
            show_success(page, f"Added '{dataset_id}' to comparison")
        except HFError as ex:
            show_error(page, str(ex))
            # Remove the placeholder on failure
            state["selections"] = [s for s in state["selections"] if s.get("id") != dataset_id]
            _refresh_all(page, state, content_col, chips_row, theme_mode)
        except Exception as ex:
            logger.error("Add dataset error: %s", ex, exc_info=True)
            show_error(page, str(ex))
            state["selections"] = [s for s in state["selections"] if s.get("id") != dataset_id]
            _refresh_all(page, state, content_col, chips_row, theme_mode)

    page.run_thread(_run)
    # Show immediate update with placeholder
    _refresh_all(page, state, content_col, chips_row, theme_mode)


def _remove_dataset(page: ft.Page, state: Dict[str, Any], dataset_id: str,
                    content_col: ft.Column, chips_row: ft.Row,
                    theme_mode: str) -> None:
    state["selections"] = [s for s in state["selections"] if s.get("id") != dataset_id]
    state["datasets"].pop(dataset_id, None)
    _refresh_all(page, state, content_col, chips_row, theme_mode)


def _clear_all(state: Dict[str, Any], content_col: ft.Column,
               chips_row: ft.Row, theme_mode: str) -> None:
    state["selections"] = []
    state["datasets"] = {}
    _refresh_chips(state, chips_row, theme_mode)
    _render_comparison(state, content_col, theme_mode)


def _refresh_all(page: ft.Page, state: Dict[str, Any], content_col: ft.Column,
                 chips_row: ft.Row, theme_mode: str) -> None:
    _refresh_chips(state, chips_row, theme_mode)
    _render_comparison(state, content_col, theme_mode)


def _refresh_chips(state: Dict[str, Any], chips_row: ft.Row, theme_mode: str) -> None:
    try:
        chips_row.controls.clear()
        if not state["selections"]:
            chips_row.controls.append(
                ft.Text("No datasets selected. Add some above or from your Favorites.",
                        size=11, color=muted_text_color(theme_mode))
            )
        else:
            for s in state["selections"]:
                ds_id = s.get("id", "?")
                is_loaded = ds_id in state["datasets"]
                chips_row.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.DATASET_OUTLINED, size=14,
                                        color=SUCCESS if is_loaded else WARNING),
                                ft.Text(ds_id, size=11, color=text_color(theme_mode),
                                        weight=ft.FontWeight.W_500, selectable=True,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE, icon_size=14,
                                    tooltip="Remove",
                                    on_click=lambda e, did=ds_id: _remove_dataset_chips(
                                        did, state, chips_row, content_col, theme_mode),
                                ),
                            ],
                            spacing=6, tight=True,
                        ),
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border=ft.border.all(1, border_color(theme_mode)),
                        border_radius=16,
                        bgcolor=surface_bg(theme_mode),
                    )
                )
        chips_row.update()
    except Exception:
        pass


def _remove_dataset_chips(dataset_id: str, state: Dict[str, Any],
                          chips_row: ft.Row, content_col: ft.Column,
                          theme_mode: str) -> None:
    state["selections"] = [s for s in state["selections"] if s.get("id") != dataset_id]
    state["datasets"].pop(dataset_id, None)
    _refresh_chips(state, chips_row, theme_mode)
    _render_comparison(state, content_col, theme_mode)


# --------------------------------------------------------------------------- #
# Comparison rendering
# --------------------------------------------------------------------------- #

def _render_comparison(state: Dict[str, Any], content_col: ft.Column,
                       theme_mode: str) -> None:
    try:
        content_col.controls.clear()

        selections = state["selections"]
        if not selections:
            content_col.controls.append(
                empty_view(
                    "Add datasets above to start comparing.",
                    icon=ft.Icons.COMPARE_ARROWS, theme_mode=theme_mode,
                )
            )
            content_col.update()
            return

        loaded = [s for s in selections if s.get("id") in state["datasets"]]
        if not loaded:
            content_col.controls.append(
                empty_view(
                    "Loading datasets…",
                    icon=ft.Icons.HOURGLASS_TOP, theme_mode=theme_mode,
                )
            )
            content_col.update()
            return

        # Build comparison table
        dataset_ids = [s.get("id") for s in loaded]
        datasets = [state["datasets"][did] for did in dataset_ids]

        # Find the best value for each numeric metric to highlight it
        def _is_best(idx: int, values: List[float], higher_is_better: bool = True) -> bool:
            val = values[idx]
            if val is None:
                return False
            non_none = [v for v in values if v is not None]
            if not non_none:
                return False
            best = max(non_none) if higher_is_better else min(non_none)
            return val == best and best > 0

        rows_data: List[List[Any]] = []

        # Header row: dataset IDs
        header_cells = [ft.DataCell(ft.Text("Metric", size=12,
                                            weight=ft.FontWeight.BOLD,
                                            color=muted_text_color(theme_mode)))]
        for ds in datasets:
            header_cells.append(ft.DataCell(
                ft.Column(
                    [
                        ft.Text(ds.get("id", "?"), size=11,
                                weight=ft.FontWeight.BOLD,
                                color=text_color(theme_mode), selectable=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"by {ds.get('author', '—')}", size=10,
                                color=muted_text_color(theme_mode)),
                    ],
                    spacing=0, tight=True,
                )
            ))
        rows_data.append(("header", header_cells))

        # Numeric metrics
        metric_specs = [
            ("Downloads", "downloads", True, INFO),
            ("Likes", "likes", True, WARNING),
            ("Trending Score", "trendingScore", True, SUCCESS),
            ("Total Examples", "_total_examples", True, ACCENT),
            ("Download Size", "_download_size", False, PRIMARY),
            ("Dataset Size", "_dataset_size", False, PRIMARY),
        ]

        # Pre-compute enriched stats
        enriched = []
        for ds in datasets:
            stats = get_dataset_stats(ds)
            enriched.append({
                **ds,
                "_total_examples": stats["total_examples"],
                "_download_size": stats["download_size"],
                "_dataset_size": stats["dataset_size"],
            })

        for label, key, higher_is_better, color in metric_specs:
            values = [d.get(key, 0) or 0 for d in enriched]
            cells = [ft.DataCell(ft.Text(label, size=11,
                                         color=muted_text_color(theme_mode),
                                         weight=ft.FontWeight.W_500))]
            for i, val in enumerate(values):
                is_best = _is_best(i, values, higher_is_better)
                if key in ("_download_size", "_dataset_size"):
                    display = format_bytes(val)
                elif key == "_total_examples":
                    display = format_int(val)
                else:
                    display = format_compact(val)
                cells.append(ft.DataCell(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.15, color) if is_best else None,
                        content=ft.Text(display, size=12,
                                        color=color if is_best else text_color(theme_mode),
                                        weight=ft.FontWeight.W_700 if is_best else ft.FontWeight.NORMAL),
                    )
                ))
            rows_data.append(("data", cells))

        # Last modified
        last_mod_values = [d.get("lastModified", "") for d in datasets]
        cells = [ft.DataCell(ft.Text("Last Modified", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for val in last_mod_values:
            cells.append(ft.DataCell(ft.Text(format_date(val), size=11,
                                              color=text_color(theme_mode))))
        rows_data.append(("data", cells))

        # Created
        created_values = [d.get("createdAt", "") for d in datasets]
        cells = [ft.DataCell(ft.Text("Created", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for val in created_values:
            cells.append(ft.DataCell(ft.Text(format_date(val), size=11,
                                              color=text_color(theme_mode))))
        rows_data.append(("data", cells))

        # License (from tags)
        cells = [ft.DataCell(ft.Text("License", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for ds in datasets:
            tags = ds.get("tags", []) or []
            license_tags = [t for t in tags if t.startswith("license:")]
            license_str = ", ".join(pretty_tag(t) for t in license_tags) or "—"
            cells.append(ft.DataCell(ft.Text(license_str, size=11,
                                              color=text_color(theme_mode),
                                              selectable=True)))
        rows_data.append(("data", cells))

        # Tasks
        cells = [ft.DataCell(ft.Text("Tasks", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for ds in datasets:
            tags = ds.get("tags", []) or []
            parsed = parse_tags(tags)
            tasks = parsed.get("task", [])
            task_str = ", ".join(pretty_tag(t) for t in tasks) or "—"
            cells.append(ft.DataCell(ft.Text(task_str, size=11,
                                              color=text_color(theme_mode),
                                              selectable=True, max_lines=2,
                                              overflow=ft.TextOverflow.ELLIPSIS)))
        rows_data.append(("data", cells))

        # Modalities
        cells = [ft.DataCell(ft.Text("Modalities", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for ds in datasets:
            tags = ds.get("tags", []) or []
            parsed = parse_tags(tags)
            mods = parsed.get("modality", [])
            mod_str = ", ".join(pretty_tag(t) for t in mods) or "—"
            cells.append(ft.DataCell(ft.Text(mod_str, size=11,
                                              color=text_color(theme_mode),
                                              selectable=True)))
        rows_data.append(("data", cells))

        # Size category
        cells = [ft.DataCell(ft.Text("Size Category", size=11,
                                     color=muted_text_color(theme_mode),
                                     weight=ft.FontWeight.W_500))]
        for ds in datasets:
            tags = ds.get("tags", []) or []
            parsed = parse_tags(tags)
            sizes = parsed.get("size", [])
            size_str = ", ".join(pretty_tag(t) for t in sizes) or "—"
            cells.append(ft.DataCell(ft.Text(size_str, size=11,
                                              color=text_color(theme_mode))))
        rows_data.append(("data", cells))

        # Build the DataTable
        # The first row is the header — we put it as a regular DataRow with bold style
        data_rows = []
        for kind, cells in rows_data:
            data_rows.append(ft.DataRow(cells=cells))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("", size=11)),
                *[ft.DataColumn(ft.Text("", size=11)) for _ in datasets],
            ],
            rows=data_rows,
            horizontal_lines=ft.border.BorderSide(1, border_color(theme_mode)),
            heading_row_height=0,
            data_row_min_height=40,
            column_spacing=16,
            divider_thickness=0,
        )

        content_col.controls.append(
            ft.Container(
                padding=ft.padding.all(14),
                border=ft.border.all(1, border_color(theme_mode)),
                border_radius=10,
                bgcolor=surface_bg(theme_mode),
                content=ft.Column(
                    [
                        section_header("Comparison Table",
                                       theme_mode=theme_mode,
                                       subtitle="Best value in each row is highlighted"),
                        ft.Column(
                            [table],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                    ],
                    spacing=10,
                ),
            )
        )

        content_col.update()
    except Exception as ex:
        logger.error("Compare render error: %s", ex, exc_info=True)
        try:
            content_col.controls.clear()
            content_col.controls.append(error_view(str(ex), theme_mode))
            content_col.update()
        except Exception:
            pass
